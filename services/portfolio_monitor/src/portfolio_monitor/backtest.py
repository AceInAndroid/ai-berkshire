from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import artifacts_path
from .db import Database
from .indicators import annualized_metrics
from .models import BacktestRequest, BacktestResult, Bar, PortfolioConfig
from .providers import ProviderRegistry


@dataclass
class StrategyState:
    stage: int = 0
    weights: dict[str, float] | None = None


class PortfolioBacktester:
    """Daily, next-open execution backtester.

    Live fixed price anchors from 2026-07-20 are not applied to prior years. The
    historical staged strategy uses equivalent rolling MA/20-day-low rules and
    records that choice in warnings.
    """

    def __init__(self, config: PortfolioConfig, database: Database, providers: ProviderRegistry):
        self.config = config
        self.database = database
        self.providers = providers
        self.artifacts = artifacts_path()

    async def run(self, request: BacktestRequest) -> BacktestResult:
        run_id = uuid.uuid4().hex
        request_payload = request.model_dump(mode="json")
        self.database.create_backtest_run(run_id, self.config.version, request_payload)
        try:
            frames, warnings = await self._load_frames(request.start_date, request.end_date)
            result = self._simulate(run_id, request, frames, warnings)
            artifact = self.artifacts / f"backtest-{run_id}.json"
            artifact.write_text(result.model_dump_json(indent=2), encoding="utf-8")
            self.database.finish_backtest_run(run_id, result.model_dump(mode="json"), str(artifact))
            return result
        except Exception as error:
            self.database.fail_backtest_run(run_id, str(error))
            raise

    async def _load_frames(self, start: date, end: date) -> tuple[dict[str, pd.DataFrame], list[str]]:
        frames: dict[str, pd.DataFrame] = {}
        warnings: list[str] = []
        symbols = [item.symbol for item in self.config.instruments if item.target_amount_cny > 0]
        for symbol in symbols:
            bars = await self.providers.history(symbol, start, end)
            if len(bars) < 25:
                warnings.append(f"{symbol}仅有{len(bars)}根K线，已从回测中排除")
                continue
            frames[symbol] = self._frame(bars)
        if "510300.SH" not in frames or "159995.SZ" not in frames:
            raise ValueError("backtest requires at least 510300.SH and 159995.SZ history")
        return frames, warnings

    @staticmethod
    def _frame(bars: list[Bar]) -> pd.DataFrame:
        frame = pd.DataFrame(
            [{"date": bar.trade_date, "open": bar.open, "high": bar.high, "low": bar.low, "close": bar.close, "volume": bar.volume} for bar in bars]
        ).set_index("date").sort_index()
        for window in (5, 20, 60):
            frame[f"ma{window}"] = frame["close"].rolling(window).mean()
        frame["low20"] = frame["low"].rolling(20).min()
        frame["ret5"] = frame["close"].pct_change(5)
        frame["ret20"] = frame["close"].pct_change(20)
        frame["vol20"] = frame["volume"].rolling(20).mean()
        frame["volume_ratio"] = frame["volume"] / frame["vol20"]
        return frame

    def _simulate(
        self,
        run_id: str,
        request: BacktestRequest,
        frames: dict[str, pd.DataFrame],
        warnings: list[str],
    ) -> BacktestResult:
        common_dates = sorted(set.intersection(*(set(frame.index) for frame in frames.values())))
        if len(common_dates) < 30:
            raise ValueError("fewer than 30 common trading days")
        dates = common_dates[20:]
        staged = self._run_strategy(dates, frames, request.initial_capital_cny, mode="staged")
        static = self._run_strategy(dates, frames, request.initial_capital_cny, mode="static")
        no_tech = self._run_strategy(dates, frames, request.initial_capital_cny, mode="no_technology")
        warnings.append("历史阶段规则使用滚动均线和20日低点归一化，未把2026-07-20固定价格锚点倒推到历史。")
        return BacktestResult(
            run_id=run_id,
            status="completed",
            start_date=dates[0],
            end_date=dates[-1],
            metrics=staged["metrics"],
            comparisons={"static_42_58": static["metrics"], "without_technology": no_tech["metrics"]},
            trades=staged["trades"],
            stage_changes=staged["stage_changes"],
            equity_curve=staged["equity_curve"],
            warnings=warnings,
        )

    def _run_strategy(
        self, dates: list[date], frames: dict[str, pd.DataFrame], initial_capital: float, mode: str
    ) -> dict[str, Any]:
        target_weights = {
            item.symbol: item.target_amount_cny / self.config.initial_capital_cny
            for item in self.config.instruments
            if item.target_amount_cny > 0 and item.symbol in frames
        }
        if mode == "no_technology":
            removed = sum(weight for symbol, weight in target_weights.items() if self.config.instrument_map()[symbol].module == "technology")
            target_weights = {symbol: weight for symbol, weight in target_weights.items() if self.config.instrument_map()[symbol].module != "technology"}
            # Keep removed risk budget in cash; no synthetic security is created.
            cash_reserve = removed
        else:
            cash_reserve = 0.0
        cash = initial_capital
        quantities = {symbol: 0.0 for symbol in target_weights}
        current_weights = {symbol: 0.0 for symbol in target_weights}
        pending_weights: dict[str, float] | None = None
        pending_signal_date: date | None = None
        trades: list[dict[str, Any]] = []
        stage_changes: list[dict[str, Any]] = []
        curve: list[dict[str, Any]] = []
        stage = 0
        peak = initial_capital

        for index, day in enumerate(dates):
            if index > 0 and cash > 0:
                cash *= 1 + self.config.costs.annual_cash_yield / 252
            # Execute yesterday's close signal at today's open: explicit no-lookahead.
            if pending_weights is not None:
                prices = {symbol: float(frames[symbol].loc[day, "open"]) for symbol in quantities}
                portfolio_value = cash + sum(quantities[symbol] * prices.get(symbol, float(frames[symbol].loc[day, "open"])) for symbol in quantities)
                cash, trade_rows = self._rebalance(day, portfolio_value, cash, quantities, pending_weights, prices)
                for trade in trade_rows:
                    trade["signal_date"] = pending_signal_date.isoformat() if pending_signal_date else None
                trades.extend(trade_rows)
                current_weights = pending_weights
                pending_weights = None
                pending_signal_date = None

            closes = {symbol: float(frames[symbol].loc[day, "close"]) for symbol in quantities}
            portfolio_value = cash + sum(quantities[symbol] * closes[symbol] for symbol in quantities)
            peak = max(peak, portfolio_value)
            drawdown = portfolio_value / peak - 1
            curve.append({"date": day.isoformat(), "value": portfolio_value, "drawdown": drawdown, "stage": stage})

            if index == len(dates) - 1:
                continue
            if mode == "static" or mode == "no_technology":
                if index == 0:
                    pending_weights = target_weights.copy()
                    pending_signal_date = day
                continue

            desired_stage = self._historical_stage(day, frames)
            if drawdown <= -0.08:
                desired_stage = min(desired_stage, 1)
            if drawdown <= -0.12:
                desired_stage = 0
            if index == 0 or desired_stage != stage:
                if desired_stage != stage:
                    stage_changes.append({"signal_date": day.isoformat(), "execution_date": dates[index + 1].isoformat(), "from": stage, "to": desired_stage})
                stage = desired_stage
                pending_weights = self._weights_for_stage(target_weights, stage)
                pending_signal_date = day

        series = pd.Series(
            [row["value"] for row in curve],
            index=pd.to_datetime([row["date"] for row in curve]),
            dtype=float,
        )
        metrics = annualized_metrics(series)
        metrics["turnover"] = float(sum(abs(row["amount_cny"]) for row in trades) / initial_capital)
        metrics["trade_count"] = float(len(trades))
        metrics["ending_value"] = float(series.iloc[-1])
        return {"metrics": metrics, "trades": trades, "stage_changes": stage_changes, "equity_curve": curve}

    def _historical_stage(self, day: date, frames: dict[str, pd.DataFrame]) -> int:
        chip = frames["159995.SZ"].loc[day]
        broad = frames["510300.SH"].loc[day]
        communication = frames.get("515050.SH")
        equipment = frames.get("159516.SZ")
        near_low = chip["close"] <= chip["low20"] * 1.05 and chip["ret20"] <= -0.10
        stage = 1 if near_low else 0
        if chip["close"] > chip["ma5"] and broad["close"] > broad["ma5"]:
            stage = max(stage, 2)
        comm_ok = True if communication is None else communication.loc[day, "close"] > communication.loc[day, "ma20"]
        if chip["close"] > chip["ma20"] and chip["ret5"] > broad["ret5"] and comm_ok:
            stage = max(stage, 3)
        if equipment is not None:
            row = equipment.loc[day]
            if stage >= 3 and row["close"] > row["ma20"] and row["ret5"] > 0:
                stage = 4
        return stage

    def _weights_for_stage(self, base: dict[str, float], stage_number: int) -> dict[str, float]:
        desired = {symbol: weight for symbol, weight in base.items() if self.config.instrument_map()[symbol].module != "technology"}
        if stage_number > 0:
            stage = next(item for item in self.config.technology_stages if item.stage == stage_number)
            for symbol, amount in stage.allocations.items():
                if symbol in base:
                    desired[symbol] = amount / self.config.initial_capital_cny
        return desired

    def _rebalance(
        self,
        day: date,
        portfolio_value: float,
        cash: float,
        quantities: dict[str, float],
        weights: dict[str, float],
        prices: dict[str, float],
    ) -> tuple[float, list[dict[str, Any]]]:
        trades = []
        commission_rate = self.config.costs.commission_rate
        slippage = self.config.costs.slippage_rate
        minimum_commission = self.config.costs.minimum_commission_cny
        for symbol in quantities:
            price = prices[symbol]
            target_value = portfolio_value * weights.get(symbol, 0)
            current_value = quantities[symbol] * price
            difference = target_value - current_value
            if abs(difference) < max(portfolio_value * 0.002, 1000):
                continue
            side = "BUY" if difference > 0 else "SELL"
            execution_price = price * (1 + slippage if side == "BUY" else 1 - slippage)
            quantity = abs(difference) / execution_price
            amount = quantity * execution_price
            if amount <= 1e-9:
                continue
            commission = max(amount * commission_rate, minimum_commission)
            if side == "BUY":
                affordable = max(cash - commission, 0)
                amount = min(amount, affordable)
                quantity = amount / execution_price if execution_price else 0
                if quantity <= 0:
                    continue
                cash -= amount + commission
                quantities[symbol] += quantity
            else:
                quantity = min(quantity, quantities[symbol])
                amount = quantity * execution_price
                cash += amount - commission
                quantities[symbol] -= quantity
            trades.append({
                "execution_date": day.isoformat(), "symbol": symbol, "side": side,
                "quantity": quantity, "price": execution_price, "amount_cny": amount,
                "commission_cny": commission,
            })
        return cash, trades
