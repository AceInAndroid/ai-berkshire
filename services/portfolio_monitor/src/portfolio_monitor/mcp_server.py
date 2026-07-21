from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from .dashboard import register_dashboard_routes
from .models import BacktestRequest, TransactionInput, TransactionType
from .service import PortfolioMonitorService


def _transaction(
    transaction_type: str,
    symbol: str | None,
    quantity: float,
    price: float,
    fees: float,
    traded_at: str,
    idempotency_key: str,
    notes: str | None,
) -> TransactionInput:
    return TransactionInput(
        transaction_type=TransactionType(transaction_type.upper()),
        symbol=symbol,
        quantity=quantity,
        price=price,
        fees=fees,
        traded_at=datetime.fromisoformat(traded_at.replace("Z", "+00:00")),
        idempotency_key=idempotency_key,
        notes=notes,
    )


def create_mcp(service: PortfolioMonitorService | None = None) -> FastMCP:
    monitor = service or PortfolioMonitorService()
    runtime = monitor.config.runtime
    server = FastMCP(
        name="AI Berkshire Portfolio Monitor",
        instructions=(
            "Read-only investment research and portfolio-accounting service. "
            "It never places, cancels, replaces, finances, or routes broker orders."
        ),
        host=runtime.http_host,
        port=runtime.http_port,
        streamable_http_path=runtime.streamable_http_path,
        json_response=True,
    )
    register_dashboard_routes(server, monitor)

    @server.tool(description="Return current assets, P&L, drawdown, module weights and alert summary.")
    async def get_portfolio_dashboard(refresh: bool = False) -> dict[str, Any]:
        return await monitor.get_dashboard(refresh=refresh)

    @server.tool(description="Return total return, TWR, XIRR, realized/unrealized P&L and module contribution.")
    async def get_portfolio_performance(refresh: bool = False) -> dict[str, Any]:
        dashboard = await monitor.get_dashboard(refresh=refresh)
        return dashboard["performance"]

    @server.tool(description="Return one of cash, fixed_income, gold, dividend, broad_market or technology module status.")
    async def get_module_status(module: str) -> dict[str, Any]:
        return await monitor.get_module_status(module)

    @server.tool(description="Return market breadth, deleveraging and risk-appetite regime classification.")
    async def get_market_regime(refresh: bool = True) -> dict[str, Any]:
        if refresh:
            result = await monitor.scan(persist=False, send_alerts=False)
            return result["market_regime"]
        return monitor.database.get_state("market_regime", {})

    @server.tool(description="Return deterministic eligible, blocked, watch and reduce recommendations.")
    async def get_buy_signals() -> list[dict[str, Any]]:
        return await monitor.get_buy_signals()

    @server.tool(description="Return technology Beta stage, drawdown, hard rules and allowed actions.")
    async def get_beta_risk() -> dict[str, Any]:
        return await monitor.get_beta_risk()

    @server.tool(description="Return stored daily price/volume/indicator input bars for a symbol.")
    def get_indicator_series(symbol: str, limit: int = 120) -> list[dict[str, Any]]:
        return monitor.get_indicator_series(symbol, limit=max(1, min(limit, 1000)))

    @server.tool(description="List open, acknowledged or historical alerts, optionally filtered by severity.")
    def list_alerts(status: str | None = None, severity: str | None = None) -> list[dict[str, Any]]:
        return monitor.database.list_alerts(status=status, severity=severity)

    @server.tool(description="Run a no-lookahead three-way portfolio backtest and return its run result.")
    async def run_portfolio_backtest(
        start_date: str,
        end_date: str,
        initial_capital_cny: float = 1_000_000,
        use_index_proxies: bool = False,
    ) -> dict[str, Any]:
        request = BacktestRequest(
            start_date=start_date,
            end_date=end_date,
            initial_capital_cny=initial_capital_cny,
            use_index_proxies=use_index_proxies,
        )
        return await monitor.run_backtest(request)

    @server.tool(description="Fetch a previously stored backtest result by run ID.")
    def get_backtest_result(run_id: str) -> dict[str, Any]:
        result = monitor.get_backtest_result(run_id)
        if result is None:
            raise ValueError(f"backtest run not found: {run_id}")
        return result

    @server.tool(description="Return provider, database, data freshness and safety health.")
    async def health_check() -> dict[str, Any]:
        return await monitor.health_check()

    @server.tool(description="Preview accounting and allocation impact. This never sends a broker order.")
    def preview_transaction(
        transaction_type: str,
        traded_at: str,
        idempotency_key: str,
        symbol: str | None = None,
        quantity: float = 0,
        price: float = 0,
        fees: float = 0,
        notes: str | None = None,
    ) -> dict[str, Any]:
        tx = _transaction(transaction_type, symbol, quantity, price, fees, traded_at, idempotency_key, notes)
        return monitor.preview_transaction(tx)

    @server.tool(description="Record a transaction already completed outside this service. No broker connection is used.")
    def record_transaction(
        transaction_type: str,
        traded_at: str,
        idempotency_key: str,
        symbol: str | None = None,
        quantity: float = 0,
        price: float = 0,
        fees: float = 0,
        notes: str | None = None,
    ) -> dict[str, Any]:
        tx = _transaction(transaction_type, symbol, quantity, price, fees, traded_at, idempotency_key, notes)
        return monitor.record_transaction(tx)

    @server.tool(description="Correct an accounting record while preserving the original audit row.")
    def correct_transaction(
        transaction_id: int,
        transaction_type: str,
        traded_at: str,
        idempotency_key: str,
        symbol: str | None = None,
        quantity: float = 0,
        price: float = 0,
        fees: float = 0,
        notes: str | None = None,
    ) -> dict[str, Any]:
        replacement = _transaction(
            transaction_type, symbol, quantity, price, fees, traded_at, idempotency_key, notes
        )
        return monitor.correct_transaction(transaction_id, replacement)

    @server.tool(description="Import a local CSV of already-completed transactions into the accounting ledger.")
    def import_positions(csv_path: str, idempotency_prefix: str = "import") -> dict[str, Any]:
        return monitor.import_positions(csv_path, idempotency_prefix=idempotency_prefix)

    @server.tool(description="Acknowledge an alert in the local audit ledger.")
    def acknowledge_alert(alert_id: int) -> dict[str, Any]:
        monitor.alerts.acknowledge(alert_id)
        return {"alert_id": alert_id, "status": "acknowledged"}

    @server.tool(description="Temporarily snooze a non-hard-risk alert. Hard risk alerts cannot be snoozed.")
    def snooze_alert(alert_id: int, minutes: int = 30) -> dict[str, Any]:
        if minutes <= 0 or minutes > 7 * 24 * 60:
            raise ValueError("minutes must be between 1 and 10080")
        monitor.alerts.snooze(alert_id, minutes)
        return {"alert_id": alert_id, "status": "snoozed", "minutes": minutes}

    @server.resource("portfolio://policy/current", mime_type="application/json")
    def current_policy() -> str:
        return json.dumps(monitor.config.model_dump(mode="json"), ensure_ascii=False, indent=2)

    @server.resource("portfolio://snapshot/latest", mime_type="application/json")
    def latest_snapshot() -> str:
        return json.dumps(monitor.database.latest_portfolio_snapshot() or {}, ensure_ascii=False, indent=2)

    @server.resource("portfolio://alerts/open", mime_type="application/json")
    def open_alerts() -> str:
        return json.dumps(monitor.database.list_alerts(status="open"), ensure_ascii=False, indent=2)

    @server.resource("portfolio://backtests/{run_id}", mime_type="application/json")
    def backtest_resource(run_id: str) -> str:
        return json.dumps(monitor.get_backtest_result(run_id) or {}, ensure_ascii=False, indent=2)

    @server.resource("portfolio://data-health", mime_type="application/json")
    async def data_health() -> str:
        return json.dumps(await monitor.health_check(), ensure_ascii=False, indent=2, default=str)

    @server.prompt(description="Generate a disciplined daily review from current portfolio and market state.")
    async def daily_portfolio_review() -> str:
        dashboard = await monitor.get_dashboard(refresh=False)
        payload = json.dumps(dashboard, ensure_ascii=False, default=str)
        return (
            "请基于以下结构化数据生成每日组合复盘。必须区分事实、规则触发和解释；"
            "列出今日可执行动作、被阻断动作、风险升级、数据缺口；不得建议突破配置硬上限，"
            "不得臆造下单。\n\n" + payload
        )

    @server.prompt(description="Translate a technology Beta alert into a concise evidence-based action explanation.")
    def explain_beta_alert(alert_id: int) -> str:
        alert = next((row for row in monitor.database.list_alerts() if int(row["id"]) == alert_id), None)
        if not alert:
            raise ValueError(f"alert not found: {alert_id}")
        return (
            "请解释以下科技Beta告警。输出：触发规则、证据、允许动作、禁止动作、失效条件、"
            "数据时间。不得修改阶段金额、支撑位或风险阈值。\n\n"
            + json.dumps(alert, ensure_ascii=False, default=str)
        )

    return server


mcp = create_mcp()


if __name__ == "__main__":
    mcp.run()
