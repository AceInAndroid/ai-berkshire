from pathlib import Path

import pytest

from portfolio_monitor.providers import FixtureProvider, ProviderRegistry
from portfolio_monitor.service import PortfolioMonitorService


@pytest.fixture
def fixture_service(config, database):
    fixture = Path(__file__).parent / "fixtures" / "market_20260720.json"
    return PortfolioMonitorService(
        config=config,
        database=database,
        providers=ProviderRegistry(FixtureProvider(fixture)),
    )


@pytest.mark.asyncio
async def test_fresh_and_cached_dashboard_share_the_same_contract(fixture_service):
    fresh = await fixture_service.scan(send_alerts=False)
    cached = await fixture_service.get_dashboard(refresh=False)

    assert fresh.keys() == cached.keys()
    assert cached["market_context"] == fresh["market_context"]
    assert cached["market_regime"] == fresh["market_regime"]
    assert cached["recommendations"] == fresh["recommendations"]
    assert cached["external_indicators"] == fresh["external_indicators"]
    assert cached["market_regime"]["regime"] == "STABILIZING"
    assert cached["market_regime"]["deleveraging_continues"] is True


@pytest.mark.asyncio
async def test_dashboard_fixture_contains_policy_authorization_and_all_instruments(fixture_service):
    dashboard = await fixture_service.get_dashboard(refresh=False)

    assert len(dashboard["policy"]["instruments"]) == 15
    assert len(dashboard["indicators"]) == 15
    assert dashboard["initial_authorization"]["risk_assets"] == {
        "minimum_cny": 105000,
        "maximum_cny": 125000,
    }
    assert dashboard["beta_risk"]["next_stage"] == 1
    assert dashboard["beta_risk"]["authorized_remaining_cny"] == 25000
    assert dashboard["portfolio_history"]
    assert dashboard["data_health"]["indicator_count"] == 15


@pytest.mark.asyncio
async def test_cached_dashboard_does_not_hit_market_providers(fixture_service, monkeypatch):
    await fixture_service.scan(send_alerts=False)

    async def provider_call_must_not_run(*_args, **_kwargs):
        raise AssertionError("cached dashboard must not request market providers")

    monkeypatch.setattr(fixture_service.providers, "quotes", provider_call_must_not_run)
    dashboard = await fixture_service.get_dashboard(refresh=False)

    assert dashboard["market_regime"]["regime"] == "STABILIZING"
    assert len(dashboard["indicators"]) == 15
