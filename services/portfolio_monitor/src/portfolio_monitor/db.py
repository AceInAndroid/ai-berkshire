from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .config import CONFIG_ROOT, database_path
from .models import AlertRecord, Bar, PortfolioConfig, TransactionInput, TransactionType


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = database_path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        migrations_dir = CONFIG_ROOT / "migrations"
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
            for migration in sorted(migrations_dir.glob("*.sql")):
                if migration.stem in applied:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (migration.stem, datetime.now(UTC).isoformat()),
                )

    def seed_instruments(self, config: PortfolioConfig) -> None:
        with self.connect() as connection:
            for item in config.instruments:
                connection.execute(
                    """
                    INSERT INTO instruments(symbol, name, module, role, target_amount_cny, alternative_for, config_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                      name=excluded.name,
                      module=excluded.module,
                      role=excluded.role,
                      target_amount_cny=excluded.target_amount_cny,
                      alternative_for=excluded.alternative_for,
                      config_version=excluded.config_version
                    """,
                    (
                        item.symbol,
                        item.name,
                        item.module,
                        item.role,
                        item.target_amount_cny,
                        item.alternative_for,
                        config.version,
                    ),
                )

    def record_transaction(self, tx: TransactionInput, corrected_from_id: int | None = None) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM transactions WHERE idempotency_key=?", (tx.idempotency_key,)
            ).fetchone()
            if existing:
                return dict(existing) | {"duplicate": True}
            cursor = connection.execute(
                """
                INSERT INTO transactions(
                  transaction_type, symbol, quantity, price, fees, traded_at,
                  idempotency_key, notes, corrected_from_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tx.transaction_type.value,
                    tx.symbol,
                    tx.quantity,
                    tx.price,
                    tx.fees,
                    tx.traded_at.isoformat(),
                    tx.idempotency_key,
                    tx.notes,
                    corrected_from_id,
                    now,
                ),
            )
            tx_id = cursor.lastrowid
            self._rebuild_positions(connection)
            row = connection.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
            return dict(row) | {"duplicate": False}

    def correct_transaction(self, transaction_id: int, replacement: TransactionInput) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM transactions WHERE id=? AND status='active'", (transaction_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"active transaction {transaction_id} not found")
            duplicate = connection.execute(
                "SELECT id FROM transactions WHERE idempotency_key=?", (replacement.idempotency_key,)
            ).fetchone()
            if duplicate:
                raise ValueError(f"replacement idempotency key already exists: {replacement.idempotency_key}")
            connection.execute("UPDATE transactions SET status='corrected' WHERE id=?", (transaction_id,))
            cursor = connection.execute(
                """
                INSERT INTO transactions(
                  transaction_type, symbol, quantity, price, fees, traded_at,
                  idempotency_key, notes, corrected_from_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (replacement.transaction_type.value, replacement.symbol, replacement.quantity, replacement.price,
                 replacement.fees, replacement.traded_at.isoformat(), replacement.idempotency_key,
                 replacement.notes, transaction_id, now),
            )
            self._rebuild_positions(connection)
            replacement_row = connection.execute("SELECT * FROM transactions WHERE id=?", (cursor.lastrowid,)).fetchone()
            return dict(replacement_row) | {"duplicate": False}

    def list_transactions(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM transactions WHERE status='active' ORDER BY traded_at, id"
            ).fetchall()
            return [dict(row) for row in rows]

    def _rebuild_positions(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            "SELECT * FROM transactions WHERE status='active' ORDER BY traded_at, id"
        ).fetchall()
        positions: dict[str, dict[str, float]] = {}
        for row in rows:
            tx_type = TransactionType(row["transaction_type"])
            symbol = row["symbol"]
            if tx_type not in (TransactionType.BUY, TransactionType.SELL) or not symbol:
                continue
            position = positions.setdefault(
                symbol, {"quantity": 0.0, "average_cost": 0.0, "realized_pnl": 0.0}
            )
            quantity = float(row["quantity"])
            price = float(row["price"])
            fees = float(row["fees"])
            if tx_type == TransactionType.BUY:
                new_quantity = position["quantity"] + quantity
                if new_quantity <= 0:
                    raise ValueError(f"invalid buy quantity for {symbol}")
                total_cost = position["quantity"] * position["average_cost"] + quantity * price + fees
                position["quantity"] = new_quantity
                position["average_cost"] = total_cost / new_quantity
            else:
                if quantity > position["quantity"] + 1e-9:
                    raise ValueError(f"sell quantity exceeds position for {symbol}")
                position["realized_pnl"] += quantity * (price - position["average_cost"]) - fees
                position["quantity"] -= quantity
                if abs(position["quantity"]) < 1e-9:
                    position["quantity"] = 0
                    position["average_cost"] = 0
        connection.execute("DELETE FROM positions")
        now = datetime.now(UTC).isoformat()
        for symbol, values in positions.items():
            connection.execute(
                "INSERT INTO positions(symbol, quantity, average_cost, realized_pnl, updated_at) VALUES (?, ?, ?, ?, ?)",
                (symbol, values["quantity"], values["average_cost"], values["realized_pnl"], now),
            )

    def list_positions(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM positions ORDER BY symbol")]

    def cash_balance(self, initial_capital: float) -> float:
        cash = initial_capital
        for row in self.list_transactions():
            tx_type = TransactionType(row["transaction_type"])
            gross = float(row["quantity"]) * float(row["price"])
            fees = float(row["fees"])
            if tx_type == TransactionType.BUY:
                cash -= gross + fees
            elif tx_type == TransactionType.SELL:
                cash += gross - fees
            elif tx_type in (TransactionType.DEPOSIT, TransactionType.DIVIDEND):
                cash += float(row["price"])
            elif tx_type in (TransactionType.WITHDRAWAL, TransactionType.FEE):
                cash -= float(row["price"])
        return cash

    def upsert_bars(self, bars: list[Bar], fetched_at: datetime | None = None) -> None:
        fetched = (fetched_at or datetime.now(UTC)).isoformat()
        with self.connect() as connection:
            for bar in bars:
                connection.execute(
                    """
                    INSERT INTO market_bars(
                      symbol, trade_date, interval, open, high, low, close,
                      volume, amount, source, fetched_at
                    ) VALUES (?, ?, '1d', ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, trade_date, interval, source) DO UPDATE SET
                      open=excluded.open, high=excluded.high, low=excluded.low,
                      close=excluded.close, volume=excluded.volume, amount=excluded.amount,
                      fetched_at=excluded.fetched_at
                    """,
                    (
                        bar.symbol,
                        bar.trade_date.isoformat(),
                        bar.open,
                        bar.high,
                        bar.low,
                        bar.close,
                        bar.volume,
                        bar.amount,
                        bar.source,
                        fetched,
                    ),
                )

    def load_bars(self, symbol: str, source: str | None = None) -> list[Bar]:
        query = "SELECT * FROM market_bars WHERE symbol=? AND interval='1d'"
        params: list[Any] = [symbol]
        if source:
            query += " AND source=?"
            params.append(source)
        query += " ORDER BY trade_date"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            Bar(
                symbol=row["symbol"],
                trade_date=row["trade_date"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                amount=row["amount"],
                source=row["source"],
            )
            for row in rows
        ]

    def save_indicator(self, symbol: str, data_as_of: datetime, payload: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO indicator_snapshots(symbol, data_as_of, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(symbol, data_as_of) DO UPDATE SET payload_json=excluded.payload_json
                """,
                (symbol, data_as_of.isoformat(), json.dumps(payload, ensure_ascii=False, default=str)),
            )

    def latest_indicators(self) -> dict[str, dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT i.symbol, i.payload_json FROM indicator_snapshots i
                INNER JOIN (
                  SELECT symbol, MAX(data_as_of) AS max_time
                  FROM indicator_snapshots GROUP BY symbol
                ) latest ON latest.symbol=i.symbol AND latest.max_time=i.data_as_of
                """
            ).fetchall()
        return {row["symbol"]: json.loads(row["payload_json"]) for row in rows}

    def save_portfolio_snapshot(self, payload: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO portfolio_snapshots(data_as_of, total_assets, cash, drawdown, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(data_as_of) DO UPDATE SET
                  total_assets=excluded.total_assets, cash=excluded.cash,
                  drawdown=excluded.drawdown, payload_json=excluded.payload_json
                """,
                (
                    str(payload["data_as_of"]),
                    payload["total_assets"],
                    payload["cash"],
                    payload["drawdown"],
                    json.dumps(payload, ensure_ascii=False, default=str),
                ),
            )

    def latest_portfolio_snapshot(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM portfolio_snapshots ORDER BY data_as_of DESC LIMIT 1"
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def portfolio_history(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM portfolio_snapshots ORDER BY data_as_of"
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def upsert_alert(self, alert: AlertRecord) -> tuple[int, bool]:
        payload = json.dumps(alert.payload, ensure_ascii=False, default=str)
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id, severity, status FROM alerts WHERE dedup_key=?", (alert.dedup_key,)
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE alerts SET last_triggered_at=?, message=?, payload_json=?, severity=?
                    WHERE id=?
                    """,
                    (
                        alert.last_triggered_at.isoformat(),
                        alert.message,
                        payload,
                        alert.severity.value,
                        existing["id"],
                    ),
                )
                return int(existing["id"]), False
            cursor = connection.execute(
                """
                INSERT INTO alerts(
                  dedup_key, rule_id, symbol, module, severity, status, message,
                  payload_json, first_triggered_at, last_triggered_at,
                  acknowledged_at, snoozed_until, delivery_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.dedup_key,
                    alert.rule_id,
                    alert.symbol,
                    alert.module,
                    alert.severity.value,
                    alert.status,
                    alert.message,
                    payload,
                    alert.first_triggered_at.isoformat(),
                    alert.last_triggered_at.isoformat(),
                    alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                    alert.snoozed_until.isoformat() if alert.snoozed_until else None,
                    alert.delivery_status,
                ),
            )
            return int(cursor.lastrowid), True

    def list_alerts(self, status: str | None = None, severity: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM alerts WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status=?"
            params.append(status)
        if severity:
            query += " AND severity=?"
            params.append(severity)
        query += " ORDER BY last_triggered_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def update_alert(self, alert_id: int, **fields: Any) -> None:
        allowed = {"status", "acknowledged_at", "snoozed_until", "delivery_status"}
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return
        assignments = ", ".join(f"{key}=?" for key in updates)
        values = [value.isoformat() if isinstance(value, datetime) else value for value in updates.values()]
        with self.connect() as connection:
            connection.execute(f"UPDATE alerts SET {assignments} WHERE id=?", values + [alert_id])

    def set_state(self, key: str, value: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO system_state(key, value_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False, default=str), datetime.now(UTC).isoformat()),
            )

    def get_state(self, key: str, default: Any = None) -> Any:
        with self.connect() as connection:
            row = connection.execute("SELECT value_json FROM system_state WHERE key=?", (key,)).fetchone()
        return json.loads(row["value_json"]) if row else default

    def create_backtest_run(self, run_id: str, config_version: str, request: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO backtest_runs(
                  run_id, status, config_version, start_date, end_date,
                  request_json, created_at
                ) VALUES (?, 'running', ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    config_version,
                    request["start_date"],
                    request["end_date"],
                    json.dumps(request, ensure_ascii=False, default=str),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def finish_backtest_run(self, run_id: str, result: dict[str, Any], artifact_path: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE backtest_runs SET status='completed', result_json=?, artifact_path=?, completed_at=?
                WHERE run_id=?
                """,
                (
                    json.dumps(result, ensure_ascii=False, default=str),
                    artifact_path,
                    datetime.now(UTC).isoformat(),
                    run_id,
                ),
            )

    def fail_backtest_run(self, run_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE backtest_runs SET status='failed', error=?, completed_at=? WHERE run_id=?",
                (error, datetime.now(UTC).isoformat(), run_id),
            )

    def get_backtest_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM backtest_runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["request"] = json.loads(item.pop("request_json"))
        if item.get("result_json"):
            item["result"] = json.loads(item.pop("result_json"))
        else:
            item.pop("result_json", None)
        return item

    def scheduler_start(self, job_name: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO scheduler_runs(job_name, started_at, status) VALUES (?, ?, 'running')",
                (job_name, datetime.now(UTC).isoformat()),
            )
            return int(cursor.lastrowid)


    def latest_scheduler_run(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM scheduler_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        if item.get("details_json"):
            item["details"] = json.loads(item.pop("details_json"))
        else:
            item.pop("details_json", None)
        return item

    def scheduler_finish(self, run_id: int, status: str, duration_ms: float, details: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE scheduler_runs SET completed_at=?, status=?, duration_ms=?, details_json=? WHERE id=?
                """,
                (
                    datetime.now(UTC).isoformat(),
                    status,
                    duration_ms,
                    json.dumps(details, ensure_ascii=False, default=str),
                    run_id,
                ),
            )
