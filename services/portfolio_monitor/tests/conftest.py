from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from portfolio_monitor.config import load_config
from portfolio_monitor.db import Database
from portfolio_monitor.models import IndicatorSnapshot, MarketContext, PortfolioSnapshot, Position


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def database(tmp_path: Path, config):
    db = Database(tmp_path / "monitor.db")
    db.migrate()
    db.seed_instruments(config)
    return db


def indicator(symbol: str, price: float, **updates) -> IndicatorSnapshot:
    payload = dict(
        symbol=symbol,
        data_as_of=datetime.now(UTC),
        price=price,
        change_pct=0,
        ma5=price * 0.99,
        ma20=price * 0.98,
        trend="rising",
        stale=False,
        data_quality="verified",
    )
    payload.update(updates)
    return IndicatorSnapshot(**payload)


def technology_indicators(**price_overrides) -> dict[str, IndicatorSnapshot]:
    prices = {"159995.SZ": 1.28, "515050.SH": 1.10, "512480.SH": 1.12, "159516.SZ": 0.73}
    prices.update(price_overrides)
    return {symbol: indicator(symbol, price) for symbol, price in prices.items()}


def snapshot(
    technology_value: float = 0,
    technology_cost: float | None = None,
    total_assets: float = 1_000_000,
    drawdown: float = 0,
) -> PortfolioSnapshot:
    positions = []
    if technology_value or technology_cost:
        cost = technology_cost if technology_cost is not None else technology_value
        positions.append(
            Position(
                symbol="159995.SZ",
                quantity=1,
                average_cost=cost,
                market_price=technology_value,
                market_value=technology_value,
                unrealized_pnl=technology_value - cost,
                module="technology",
            )
        )
    module_values = {
        "cash": total_assets - technology_value,
        "fixed_income": 0,
        "gold": 0,
        "dividend": 0,
        "broad_market": 0,
        "technology": technology_value,
    }
    return PortfolioSnapshot(
        data_as_of=datetime.now(UTC),
        total_assets=total_assets,
        cash=module_values["cash"],
        positions_value=technology_value,
        realized_pnl=0,
        unrealized_pnl=sum(p.unrealized_pnl for p in positions),
        total_return=total_assets / 1_000_000 - 1,
        drawdown=drawdown,
        equity_weight=technology_value / total_assets,
        technology_weight=technology_value / total_assets,
        module_values=module_values,
        module_weights={key: value / total_assets for key, value in module_values.items()},
        positions=positions,
    )


def weak_context(**updates) -> MarketContext:
    payload = dict(
        data_as_of=datetime.now(UTC),
        csi300_return=1.53,
        csi1000_return=-2.83,
        advances=1783,
        declines=3734,
        limit_down_count=371,
        median_return=-2.03,
        semiconductor_breadth=0.18,
    )
    payload.update(updates)
    return MarketContext(**payload)
