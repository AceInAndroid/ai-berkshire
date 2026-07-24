from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from .config import Settings
from .models import Analyst
from .service import ResearchService


def create_mcp(service: ResearchService | None = None, settings: Settings | None = None) -> FastMCP:
    runtime = settings or (service.settings if service else Settings.from_env())
    research = service or ResearchService(runtime)
    server = FastMCP(
        name="AI Berkshire TradingAgents A-stock",
        instructions=(
            "Read-only A-share research adapter with two modes. Prefer prepare_codex_native_research: "
            "it needs no external LLM key and lets the Codex client execute the TradingAgents role "
            "workflow with its active model. start_astock_research runs the original upstream graph "
            "and requires separately configured provider credentials. No mode can trade."
        ),
        host=runtime.host,
        port=runtime.port,
        streamable_http_path="/mcp",
        json_response=True,
    )

    @server.tool(description="Start an isolated TradingAgents A-share research job and return its run ID.")
    async def start_astock_research(
        ticker: str,
        trade_date: str,
        analysts: list[Analyst] | None = None,
        research_depth: Literal[1, 3, 5] = 1,
    ) -> dict[str, Any]:
        return await research.start(ticker, trade_date, analysts, research_depth)

    @server.tool(
        description=(
            "Prepare a validated TradingAgents-style role plan for execution by the active Codex "
            "model; requires no external LLM provider or API key. Analysts must use the original "
            "market/social/news/fundamentals/policy/hot_money/lockup names."
        )
    )
    def prepare_codex_native_research(
        ticker: str,
        trade_date: str,
        analysts: list[Analyst] | None = None,
        research_depth: Literal[1, 3, 5] = 1,
    ) -> dict[str, Any]:
        return research.prepare_codex_native(ticker, trade_date, analysts, research_depth)

    @server.tool(description="Return queued, running, completed, or failed status for a research run.")
    def get_astock_research_status(run_id: str) -> dict[str, Any]:
        return research.status(run_id)

    @server.tool(description="Return the stable, whitelisted result for a completed research run.")
    def get_astock_research_result(run_id: str) -> dict[str, Any]:
        return research.result(run_id)

    @server.tool(description="List recent persisted A-share research runs without returning report bodies.")
    def list_astock_research_runs(limit: int = 50) -> list[dict[str, Any]]:
        return research.list_runs(limit)

    @server.tool(description="Return adapter, upstream runtime, concurrency, and read-only safety health.")
    def health_check() -> dict[str, Any]:
        return research.health()

    return server


mcp = create_mcp()
