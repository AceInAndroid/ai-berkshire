import pytest

from portfolio_monitor.mcp_server import create_mcp
from portfolio_monitor.service import PortfolioMonitorService


@pytest.mark.asyncio
async def test_mcp_catalog_is_complete_and_has_no_broker_write_tools(config, database):
    server = create_mcp(PortfolioMonitorService(config=config, database=database))
    names = {tool.name for tool in await server.list_tools()}
    required = {"get_portfolio_dashboard", "get_portfolio_performance", "get_module_status", "get_market_regime",
                "get_buy_signals", "get_beta_risk", "get_indicator_series", "list_alerts",
                "run_portfolio_backtest", "get_backtest_result", "health_check", "preview_transaction",
                "record_transaction", "correct_transaction", "import_positions", "acknowledge_alert", "snooze_alert"}
    assert required <= names
    assert not ({"submit_order", "cancel_order", "replace_order", "dca_create"} & names)
    resources = {str(resource.uri) for resource in await server.list_resources()}
    assert "portfolio://policy/current" in resources
    assert "portfolio://data-health" in resources
    assert {prompt.name for prompt in await server.list_prompts()} == {"daily_portfolio_review", "explain_beta_alert"}
