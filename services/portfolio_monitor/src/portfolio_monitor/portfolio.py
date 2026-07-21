from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from .db import Database
from .indicators import max_drawdown
from .models import IndicatorSnapshot, PortfolioConfig, PortfolioSnapshot, Position, TransactionType


class PortfolioCalculator:
    def __init__(self, config: PortfolioConfig, database: Database):
        self.config = config
        self.database = database
        self.instruments = config.instrument_map()

    def snapshot(
        self,
        indicators: dict[str, IndicatorSnapshot],
        data_as_of: datetime | None = None,
        persist: bool = True,
    ) -> PortfolioSnapshot:
        data_as_of = data_as_of or datetime.now(UTC)
        raw_positions = self.database.list_positions()
        cash = self.database.cash_balance(self.config.initial_capital_cny)
        positions: list[Position] = []
        module_values = {key: 0.0 for key in self.config.modules}
        realized = 0.0
        unrealized = 0.0
        for raw in raw_positions:
            symbol = raw["symbol"]
            instrument = self.instruments.get(symbol)
            indicator = indicators.get(symbol)
            market_price = indicator.price if indicator else float(raw["average_cost"])
            quantity = float(raw["quantity"])
            average_cost = float(raw["average_cost"])
            market_value = quantity * market_price
            position_unrealized = market_value - quantity * average_cost
            position = Position(
                symbol=symbol,
                quantity=quantity,
                average_cost=average_cost,
                market_price=market_price,
                market_value=market_value,
                realized_pnl=float(raw["realized_pnl"]),
                unrealized_pnl=position_unrealized,
                module=instrument.module if instrument else None,
            )
            positions.append(position)
            if instrument:
                module_values[instrument.module] += market_value
            realized += position.realized_pnl
            unrealized += position.unrealized_pnl
        # Cash ETF positions are part of the cash module; uninvested ledger cash is added as well.
        module_values["cash"] += cash
        positions_value = sum(item.market_value for item in positions)
        total_assets = cash + positions_value
        history_values = [self.config.initial_capital_cny]
        history_values.extend(float(row["total_assets"]) for row in self.database.portfolio_history())
        history_values.append(total_assets)
        peak = max(history_values) if history_values else total_assets
        # Live risk ladders use peak-to-current drawdown. Historical maximum
        # drawdown remains available from performance().
        drawdown = max(0.0, 1 - total_assets / peak) if peak > 0 else 0.0
        module_weights = {
            key: (value / total_assets if total_assets else 0.0) for key, value in module_values.items()
        }
        equity_value = sum(module_values[key] for key in ("dividend", "broad_market", "technology"))
        snapshot = PortfolioSnapshot(
            data_as_of=data_as_of,
            total_assets=total_assets,
            cash=cash,
            positions_value=positions_value,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            total_return=(total_assets / self.config.initial_capital_cny - 1),
            drawdown=drawdown,
            equity_weight=equity_value / total_assets if total_assets else 0,
            technology_weight=module_values["technology"] / total_assets if total_assets else 0,
            module_values=module_values,
            module_weights=module_weights,
            positions=positions,
        )
        if persist:
            self.database.save_portfolio_snapshot(snapshot.model_dump(mode="json"))
        return snapshot

    def performance(self, latest: PortfolioSnapshot | None = None) -> dict[str, Any]:
        latest = latest or self.snapshot({}, persist=False)
        history = self.database.portfolio_history()
        values = [self.config.initial_capital_cny] + [float(row["total_assets"]) for row in history]
        if not history or values[-1] != latest.total_assets:
            values.append(latest.total_assets)
        twr = self._time_weighted_return(history, latest)
        cash_flows = self._external_cash_flows(latest)
        xirr = self._xirr(cash_flows)
        module_contribution: dict[str, float] = {key: 0.0 for key in self.config.modules}
        for position in latest.positions:
            if position.module:
                module_contribution[position.module] += position.realized_pnl + position.unrealized_pnl
        return {
            "data_as_of": latest.data_as_of.isoformat(),
            "total_assets": latest.total_assets,
            "cash": latest.cash,
            "total_return": latest.total_return,
            "time_weighted_return": twr,
            "xirr": xirr,
            "realized_pnl": latest.realized_pnl,
            "unrealized_pnl": latest.unrealized_pnl,
            "max_drawdown": max_drawdown(values),
            "module_contribution_cny": module_contribution,
            "module_weights": latest.module_weights,
        }

    def technology_drawdown(self, snapshot: PortfolioSnapshot) -> float:
        cost = 0.0
        pnl = 0.0
        for position in snapshot.positions:
            if position.module == "technology":
                cost += position.quantity * position.average_cost
                pnl += position.unrealized_pnl
        if cost <= 0 or pnl >= 0:
            return 0.0
        return abs(pnl / cost)

    def preview_transaction(
        self, transaction_type: TransactionType, symbol: str | None, quantity: float, price: float, fees: float
    ) -> dict[str, Any]:
        latest = self.database.latest_portfolio_snapshot()
        total_assets = float(latest["total_assets"]) if latest else self.config.initial_capital_cny
        cash = float(latest["cash"]) if latest else self.database.cash_balance(self.config.initial_capital_cny)
        gross = quantity * price
        cash_after = cash
        if transaction_type == TransactionType.BUY:
            cash_after -= gross + fees
        elif transaction_type == TransactionType.SELL:
            cash_after += gross - fees
        elif transaction_type in (TransactionType.DEPOSIT, TransactionType.DIVIDEND):
            cash_after += price
        elif transaction_type in (TransactionType.WITHDRAWAL, TransactionType.FEE):
            cash_after -= price
        instrument = self.instruments.get(symbol) if symbol else None
        current_module = (latest or {}).get("module_values", {}).get(instrument.module, 0) if instrument else 0
        module_after = current_module + gross if transaction_type == TransactionType.BUY else current_module - gross
        return {
            "transaction_type": transaction_type.value,
            "symbol": symbol,
            "gross_amount_cny": gross,
            "fees_cny": fees,
            "cash_before_cny": cash,
            "cash_after_cny": cash_after,
            "cash_below_200k": cash_after < 200_000,
            "module": instrument.module if instrument else None,
            "module_value_after_cny": module_after if instrument else None,
            "module_weight_after": module_after / total_assets if instrument and total_assets else None,
            "hard_cap_weight": self.config.modules[instrument.module].hard_cap_weight if instrument else None,
            "warning": "预览仅记录用户已在券商端完成的交易，不会发出订单。",
        }

    def _time_weighted_return(self, history: list[dict[str, Any]], latest: PortfolioSnapshot) -> float:
        if not history:
            return latest.total_return
        values = [self.config.initial_capital_cny] + [float(row["total_assets"]) for row in history]
        if values[-1] != latest.total_assets:
            values.append(latest.total_assets)
        product = 1.0
        for previous, current in zip(values, values[1:]):
            if previous:
                product *= current / previous
        return product - 1

    def _external_cash_flows(self, latest: PortfolioSnapshot) -> list[tuple[datetime, float]]:
        transactions = self.database.list_transactions()
        first_date = min(
            (datetime.fromisoformat(row["traded_at"]) for row in transactions),
            default=latest.data_as_of,
        )
        flows = [(first_date, -self.config.initial_capital_cny)]
        for row in transactions:
            tx_type = TransactionType(row["transaction_type"])
            traded_at = datetime.fromisoformat(row["traded_at"])
            if tx_type == TransactionType.DEPOSIT:
                flows.append((traded_at, -float(row["price"])))
            elif tx_type == TransactionType.WITHDRAWAL:
                flows.append((traded_at, float(row["price"])))
        flows.append((latest.data_as_of, latest.total_assets))
        return flows

    @staticmethod
    def _xirr(flows: list[tuple[datetime, float]]) -> float | None:
        if len(flows) < 2 or not any(value < 0 for _, value in flows) or not any(value > 0 for _, value in flows):
            return None
        start = min(day for day, _ in flows)

        def npv(rate: float) -> float:
            return sum(value / ((1 + rate) ** ((day - start).total_seconds() / 86400 / 365.25)) for day, value in flows)

        low, high = -0.9999, 10.0
        low_value, high_value = npv(low), npv(high)
        if math.copysign(1, low_value) == math.copysign(1, high_value):
            return None
        for _ in range(200):
            middle = (low + high) / 2
            value = npv(middle)
            if abs(value) < 1e-7:
                return middle
            if math.copysign(1, value) == math.copysign(1, low_value):
                low, low_value = middle, value
            else:
                high = middle
        return (low + high) / 2
