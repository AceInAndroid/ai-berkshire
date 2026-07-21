from pathlib import Path

import pytest

from portfolio_monitor.providers import FixtureProvider, ProviderRegistry
from portfolio_monitor.service import PortfolioMonitorService


@pytest.mark.asyncio
async def test_20260720_replay_acceptance(config, database):
    fixture = Path(__file__).parent / "fixtures" / "market_20260720.json"
    service = PortfolioMonitorService(config=config, database=database,
                                      providers=ProviderRegistry(FixtureProvider(fixture)))
    result = await service.scan(send_alerts=False)
    assert result["market_regime"]["regime"] == "STABILIZING"
    assert result["market_regime"]["deleveraging_continues"] is True
    assert result["initial_authorization"]["risk_assets"] == {"minimum_cny": 105000, "maximum_cny": 125000}
    beta = [r for r in result["recommendations"] if r["module"] == "technology" and r["status"] == "eligible"]
    assert sum(r["max_amount_cny"] for r in beta) == 25000
    assert all("data_as_of" in r and "evidence" in r and "blocking_reasons" in r and "invalidation" in r for r in result["recommendations"])
