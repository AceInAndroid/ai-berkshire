from pathlib import Path

import pytest

from tradingagents_astock_mcp.config import Settings
from tradingagents_astock_mcp.mcp_server import create_mcp
from tradingagents_astock_mcp.service import ResearchService


class FakeWorker:
    async def run(self, request, run_dir: Path):
        return {
            "schema_version": 1,
            "company_of_interest": request.ticker,
            "trade_date": request.trade_date,
            "signal": "Hold",
            "analyst_reports": {"market": "stable"},
        }


@pytest.mark.asyncio
async def test_catalog_is_read_only(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = ResearchService(settings, worker=FakeWorker())
    server = create_mcp(service)
    names = {tool.name for tool in await server.list_tools()}
    assert names == {
        "start_astock_research",
        "prepare_codex_native_research",
        "get_astock_research_status",
        "get_astock_research_result",
        "list_astock_research_runs",
        "health_check",
    }
    forbidden = {"submit_order", "place_order", "cancel_order", "shell", "execute"}
    assert not names & forbidden
    start_tool = next(tool for tool in await server.list_tools() if tool.name == "start_astock_research")
    assert set(start_tool.inputSchema["properties"]) == {
        "ticker", "trade_date", "analysts", "research_depth"
    }
    assert "api_key" not in str(start_tool.inputSchema)
    assert "base_url" not in str(start_tool.inputSchema)
    assert "worker_python" not in str([tool.inputSchema for tool in await server.list_tools()])
    await service.close()
