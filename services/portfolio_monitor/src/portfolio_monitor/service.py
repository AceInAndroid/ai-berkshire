from __future__ import annotations

import csv
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .alerts import AlertManager
from .backtest import PortfolioBacktester
from .config import load_config
from .db import Database
from .indicators import calculate_indicator
from .models import (
    BacktestRequest,
    IndicatorSnapshot,
    MarketContext,
    PortfolioConfig,
    PortfolioSnapshot,
    TransactionInput,
    TransactionType,
)
from .portfolio import PortfolioCalculator
from .providers import (
    EastmoneyProvider,
    FixtureProvider,
    LongbridgeReadOnlyProvider,
    ProviderRegistry,
    TencentProvider,
    YahooProvider,
)
from .rules import RuleEngine


class PortfolioMonitorService:
    def __init__(
        self,
        config: PortfolioConfig | None = None,
        database: Database | None = None,
        providers: ProviderRegistry | None = None,
    ):
        self.config = config or load_config()
        self.database = database or Database()
        self.providers = providers or self._default_providers()
        self.calculator = PortfolioCalculator(self.config, self.database)
        self.rules = RuleEngine(self.config)
        self.alerts = AlertManager(self.database)
        self.backtester = PortfolioBacktester(self.config, self.database, self.providers)
        self.timezone = ZoneInfo(self.config.runtime.timezone)
        self.initialize()

    def initialize(self) -> None:
        self.database.migrate()
        self.database.seed_instruments(self.config)

    def _default_providers(self) -> ProviderRegistry:
        fixture = os.getenv("PORTFOLIO_MONITOR_FIXTURE")
        if fixture:
            return ProviderRegistry(FixtureProvider(fixture))
        fallbacks = [EastmoneyProvider()]
        if os.getenv("LONGBRIDGE_MCP_URL"):
            fallbacks.insert(0, LongbridgeReadOnlyProvider())
        return ProviderRegistry(TencentProvider(), fallbacks)

    async def scan(self, persist: bool = True, send_alerts: bool = True) -> dict[str, Any]:
        now = datetime.now(UTC)
        symbols = [item.symbol for item in self.config.instruments]
        quotes, candidates = await self.providers.quotes(symbols)
        indicators: dict[str, IndicatorSnapshot] = {}
        start = now.astimezone(self.timezone).date() - timedelta(days=180)
        end = now.astimezone(self.timezone).date()
        for symbol in symbols:
            bars = self.database.load_bars(symbol)
            if not bars or bars[-1].trade_date < end - timedelta(days=5):
                try:
                    bars = await self.providers.history(symbol, start, end)
                    if bars:
                        self.database.upsert_bars(bars)
                except Exception:
                    pass
            if not bars and symbol in quotes:
                quote = quotes[symbol]
                from .models import Bar
                bars = [Bar(symbol=symbol, trade_date=quote.market_time.date(), open=quote.open or quote.price,
                            high=quote.high or quote.price, low=quote.low or quote.price, close=quote.price,
                            volume=quote.volume or 0, amount=quote.amount or 0, source=quote.source)]
            if not bars and symbol not in quotes:
                continue
            indicator = calculate_indicator(
                symbol,
                bars,
                quotes.get(symbol),
                candidates.get(symbol),
                self.config.runtime.stale_after_minutes,
                self.config.runtime.cross_source_max_deviation,
                now=now,
            )
            indicators[symbol] = indicator
            if persist:
                self.database.save_indicator(symbol, indicator.data_as_of, indicator.model_dump(mode="json"))

        context = await self.providers.market_context() or self._fallback_context(indicators, now)
        context = self._enrich_context(context, indicators)
        regime = self.rules.classify_market(context)
        snapshot = self.calculator.snapshot(indicators, data_as_of=now, persist=persist)
        recommendations = self.rules.buy_signals(snapshot, indicators, context, regime)
        alert_results = await self.alerts.process_recommendations(recommendations) if send_alerts else []
        external = await self._external_risk_indicators()
        recommendation_payload = [item.model_dump(mode="json") for item in recommendations]
        context_payload = context.model_dump(mode="json")
        regime_payload = regime.model_dump(mode="json")
        self.database.set_state("market_context", context_payload)
        self.database.set_state("market_regime", regime_payload)
        self.database.set_state("recommendations", recommendation_payload)
        self.database.set_state("external_indicators", external)
        return await self._build_dashboard_payload(
            snapshot=snapshot.model_dump(mode="json"),
            indicators={symbol: item.model_dump(mode="json") for symbol, item in indicators.items()},
            context=context_payload,
            regime=regime_payload,
            recommendations=recommendation_payload,
            external=external,
            alert_results=alert_results,
        )

    async def get_dashboard(self, refresh: bool = False) -> dict[str, Any]:
        if refresh:
            return await self.scan(persist=True, send_alerts=False)
        snapshot = self.database.latest_portfolio_snapshot()
        if not snapshot:
            return await self.scan(persist=True, send_alerts=False)
        return await self._build_dashboard_payload(
            snapshot=snapshot,
            indicators=self.database.latest_indicators(),
            context=self.database.get_state("market_context", {}),
            regime=self.database.get_state("market_regime", {}),
            recommendations=self.database.get_state("recommendations", []),
            external=self.database.get_state("external_indicators", {}),
            alert_results=[],
        )

    async def _build_dashboard_payload(
        self,
        *,
        snapshot: dict[str, Any],
        indicators: dict[str, dict[str, Any]],
        context: dict[str, Any],
        regime: dict[str, Any],
        recommendations: list[dict[str, Any]],
        external: dict[str, Any],
        alert_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        snapshot_model = PortfolioSnapshot.model_validate(snapshot)
        return {
            "data_as_of": snapshot_model.data_as_of.isoformat(),
            "config_version": self.config.version,
            "initial_authorization": self.config.initial_authorization,
            "policy": {
                "name": self.config.name,
                "initial_capital_cny": self.config.initial_capital_cny,
                "equity_weight_cap": self.config.equity_weight_cap,
                "technology_weight_cap": self.config.technology_weight_cap,
                "modules": {key: value.model_dump(mode="json") for key, value in self.config.modules.items()},
                "instruments": [item.model_dump(mode="json") for item in self.config.instruments],
            },
            "portfolio": snapshot,
            "performance": self.calculator.performance(snapshot_model),
            "market_context": context,
            "market_regime": regime,
            "recommendations": recommendations,
            "beta_risk": self._cached_beta_risk(snapshot_model, recommendations, regime),
            "portfolio_history": self.get_portfolio_history(),
            "open_alerts": self.database.list_alerts(status="open"),
            "indicators": indicators,
            "external_indicators": external,
            "alerts": alert_results,
            "data_health": await self.health_check(),
        }

    def _cached_beta_risk(
        self,
        snapshot: PortfolioSnapshot,
        recommendations: list[dict[str, Any]],
        regime: dict[str, Any],
    ) -> dict[str, Any]:
        current_value = snapshot.module_values.get("technology", 0)
        current_stage = self.rules._current_stage(current_value)
        next_stage = min(current_stage + 1, 4)
        next_policy = next(item for item in self.config.technology_stages if item.stage == next_stage)
        technology_recommendations = [item for item in recommendations if item.get("module") == "technology"]
        authorized_remaining = sum(
            float(item.get("max_amount_cny") or 0)
            for item in technology_recommendations
            if item.get("status") == "eligible"
        )
        action = "watch"
        if any(item.get("status") == "reduce" for item in technology_recommendations):
            action = "reduce"
        elif any(item.get("status") == "blocked" for item in technology_recommendations):
            action = "blocked"
        elif authorized_remaining > 0:
            action = "eligible"
        return {
            "current_stage": current_stage,
            "next_stage": next_stage,
            "technology_value_cny": current_value,
            "technology_weight": snapshot.technology_weight,
            "technology_drawdown": self.calculator.technology_drawdown(snapshot),
            "next_stage_target_cny": next_policy.cumulative_amount_cny,
            "next_stage_gap_cny": max(next_policy.cumulative_amount_cny - current_value, 0),
            "authorized_remaining_cny": authorized_remaining,
            "action": action,
            "market_regime": regime,
            "recommendations": technology_recommendations,
            "hard_rules": self.config.technology_risk,
            "stages": [item.model_dump(mode="json") for item in self.config.technology_stages],
        }

    def get_portfolio_history(self, limit: int = 120) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 2000))
        return self.database.portfolio_history()[-limit:]

    async def get_module_status(self, module: str) -> dict[str, Any]:
        if module not in self.config.modules:
            raise ValueError(f"unknown module: {module}")
        dashboard = await self.get_dashboard()
        instruments = [item.model_dump() for item in self.config.instruments if item.module == module]
        indicators = {
            symbol: payload for symbol, payload in dashboard.get("indicators", {}).items()
            if any(item["symbol"] == symbol for item in instruments)
        }
        recommendations = [
            item for item in dashboard.get("recommendations", []) if item.get("module") == module
        ]
        return {
            "module": module,
            "policy": self.config.modules[module].model_dump(),
            "actual_value_cny": dashboard["portfolio"]["module_values"].get(module, 0),
            "actual_weight": dashboard["portfolio"]["module_weights"].get(module, 0),
            "instruments": instruments,
            "indicators": indicators,
            "recommendations": recommendations,
        }

    async def get_buy_signals(self) -> list[dict[str, Any]]:
        result = await self.scan(persist=False, send_alerts=False)
        return result["recommendations"]

    async def get_beta_risk(self) -> dict[str, Any]:
        result = await self.scan(persist=False, send_alerts=False)
        snapshot = PortfolioSnapshot.model_validate(result["portfolio"])
        return {
            "data_as_of": result["data_as_of"],
            **self._cached_beta_risk(snapshot, result["recommendations"], result["market_regime"]),
        }

    def get_indicator_series(self, symbol: str, limit: int = 120) -> list[dict[str, Any]]:
        bars = self.database.load_bars(symbol)
        return [bar.model_dump(mode="json") for bar in bars[-limit:]]

    def preview_transaction(self, tx: TransactionInput) -> dict[str, Any]:
        return self.calculator.preview_transaction(tx.transaction_type, tx.symbol, tx.quantity, tx.price, tx.fees)

    def record_transaction(self, tx: TransactionInput) -> dict[str, Any]:
        if tx.transaction_type in (TransactionType.BUY, TransactionType.SELL):
            if not tx.symbol or tx.symbol not in self.config.instrument_map():
                raise ValueError("BUY/SELL symbol must be one of the configured monitored instruments")
            if tx.quantity <= 0 or tx.price <= 0:
                raise ValueError("BUY/SELL requires positive quantity and price")
        return self.database.record_transaction(tx)

    def correct_transaction(self, transaction_id: int, replacement: TransactionInput) -> dict[str, Any]:
        return self.database.correct_transaction(transaction_id, replacement)

    def import_positions(self, csv_path: str | Path, idempotency_prefix: str = "import") -> dict[str, Any]:
        path = Path(csv_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"CSV not found: {path}")
        imported = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle), start=1):
                symbol = row["symbol"].strip()
                traded_at = datetime.fromisoformat(row.get("traded_at") or datetime.now(UTC).isoformat())
                tx = TransactionInput(
                    transaction_type=TransactionType(row.get("transaction_type", "BUY").upper()),
                    symbol=symbol,
                    quantity=float(row.get("quantity") or 0),
                    price=float(row.get("price") or 0),
                    fees=float(row.get("fees") or 0),
                    traded_at=traded_at,
                    idempotency_key=row.get("idempotency_key") or f"{idempotency_prefix}:{path.name}:{index}",
                    notes=row.get("notes") or f"imported from {path.name}",
                )
                imported.append(self.record_transaction(tx))
        return {"path": str(path), "imported": len(imported), "transactions": imported}

    async def run_backtest(self, request: BacktestRequest) -> dict[str, Any]:
        result = await self.backtester.run(request)
        return result.model_dump(mode="json")

    def get_backtest_result(self, run_id: str) -> dict[str, Any] | None:
        return self.database.get_backtest_run(run_id)

    async def health_check(self) -> dict[str, Any]:
        latest = self.database.latest_portfolio_snapshot()
        indicators = self.database.latest_indicators()
        stale_symbols = [
            symbol for symbol, payload in indicators.items()
            if payload.get("stale") or payload.get("data_quality") in {"stale", "conflict"}
        ]
        provider_health = await self.providers.health()
        return {
            "status": "degraded" if stale_symbols else "ok",
            "config_version": self.config.version,
            "database": str(self.database.path),
            "database_exists": self.database.path.exists(),
            "providers": provider_health,
            "last_portfolio_snapshot": latest["data_as_of"] if latest else None,
            "latest_scheduler_run": self.database.latest_scheduler_run(),
            "indicator_count": len(indicators),
            "stale_or_conflicting_symbols": stale_symbols,
            "open_alert_count": len(self.database.list_alerts(status="open")),
            "read_only_trading": True,
            "broker_write_tools_registered": False,
        }

    def _fallback_context(self, indicators: dict[str, IndicatorSnapshot], now: datetime) -> MarketContext:
        csi300 = indicators.get("510300.SH")
        a500 = indicators.get("563360.SH")
        chip = indicators.get("159995.SZ")
        returns = [item.change_pct or 0 for item in indicators.values()]
        advances = sum(value > 0 for value in returns)
        declines = sum(value < 0 for value in returns)
        return MarketContext(
            data_as_of=now,
            csi300_return=(csi300.change_pct or 0) if csi300 else 0,
            csi1000_return=(a500.change_pct or 0) if a500 else 0,
            star50_return=(chip.change_pct or 0) if chip else 0,
            advances=advances,
            declines=declines,
            median_return=sorted(returns)[len(returns) // 2] if returns else 0,
            limit_down_count=sum(value <= -9.8 for value in returns),
        )

    def _enrich_context(self, context: MarketContext, indicators: dict[str, IndicatorSnapshot]) -> MarketContext:
        previous = self.database.get_state("market_context", {})
        csi300 = indicators.get("510300.SH")
        a500 = indicators.get("563360.SH")
        chip = indicators.get("159995.SZ")
        update: dict[str, Any] = {}
        if context.csi300_return == 0 and csi300:
            update["csi300_return"] = csi300.change_pct or 0
        if context.csi1000_return == 0 and a500:
            update["csi1000_return"] = a500.change_pct or 0
        if context.star50_return == 0 and chip:
            update["star50_return"] = chip.change_pct or 0
        if previous:
            update["advances_exceed_declines_two_days"] = (
                context.advances > context.declines and previous.get("advances", 0) > previous.get("declines", 0)
            )
            update["median_positive_two_days"] = context.median_return > 0 and previous.get("median_return", 0) > 0
            previous_regime = self.database.get_state("market_regime", {}).get("regime")
            if previous_regime:
                from .models import MarketRegime
                update["previous_regime"] = MarketRegime(previous_regime)
        return MarketContext.model_validate(context.model_dump() | update)

    async def _external_risk_indicators(self) -> dict[str, Any]:
        if isinstance(self.providers.primary, FixtureProvider):
            return self.providers.primary.payload.get(
                "external_indicators", {"status": "fixture", "data": {}}
            )
        provider = YahooProvider()
        symbols = [item["symbol"] for item in self.config.external_indicators]
        try:
            quotes = await provider.get_quotes(symbols)
        except Exception as error:
            return {"status": "unavailable", "error": str(error), "data": {}}
        return {
            "status": "ok",
            "data": {symbol: quote.model_dump(mode="json") for symbol, quote in quotes.items()},
        }
