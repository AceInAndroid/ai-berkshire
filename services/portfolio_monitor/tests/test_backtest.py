from datetime import date, datetime
from pathlib import Path

import pytest

from portfolio_monitor.backtest import PortfolioBacktester
from portfolio_monitor.models import BacktestRequest
from portfolio_monitor.providers import FixtureProvider, ProviderRegistry


@pytest.mark.asyncio
async def test_backtest_is_next_session_and_has_comparisons(config, database, tmp_path, monkeypatch):
    fixture = Path(__file__).parent / "fixtures" / "market_20260720.json"
    tester = PortfolioBacktester(config, database, ProviderRegistry(FixtureProvider(fixture)))
    tester.artifacts = tmp_path
    result = await tester.run(BacktestRequest(start_date=date(2026,3,1), end_date=date(2026,7,20)))
    assert set(result.comparisons) == {"static_42_58", "without_technology"}
    assert result.trades
    for trade in result.trades:
        assert datetime.fromisoformat(trade["execution_date"]) > datetime.fromisoformat(trade["signal_date"])
    for change in result.stage_changes:
        assert datetime.fromisoformat(change["execution_date"]) > datetime.fromisoformat(change["signal_date"])
    assert "固定价格锚点" in result.warnings[-1]
