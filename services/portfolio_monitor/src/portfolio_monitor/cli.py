from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from typing import Any

from .mcp_server import create_mcp
from .models import BacktestRequest
from .scheduler import MonitorScheduler
from .service import PortfolioMonitorService


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="portfolio-monitor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create/migrate SQLite and seed configured instruments")

    scan = subparsers.add_parser("scan", help="Fetch data and evaluate portfolio rules")
    scan.add_argument("--no-alerts", action="store_true", help="Do not deliver or persist alerts")
    scan.add_argument("--no-persist", action="store_true", help="Do not persist snapshots")

    serve = subparsers.add_parser("serve", help="Run the MCP server")
    serve.add_argument("--transport", choices=("stdio", "http"), default="stdio")

    subparsers.add_parser("scheduler", help="Run the local market-session scheduler")

    backtest = subparsers.add_parser("backtest", help="Run staged/static/no-technology comparisons")
    backtest.add_argument("--start", required=True, type=date.fromisoformat)
    backtest.add_argument("--end", required=True, type=date.fromisoformat)
    backtest.add_argument("--capital", type=float, default=1_000_000)
    backtest.add_argument("--use-index-proxies", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    service = PortfolioMonitorService()

    if args.command == "init-db":
        _print({"status": "ok", "database": str(service.database.path), "config_version": service.config.version})
        return
    if args.command == "scan":
        result = asyncio.run(service.scan(persist=not args.no_persist, send_alerts=not args.no_alerts))
        _print(result)
        return
    if args.command == "serve":
        server = create_mcp(service)
        server.run(transport="stdio" if args.transport == "stdio" else "streamable-http")
        return
    if args.command == "scheduler":
        MonitorScheduler(service).start()
        return
    if args.command == "backtest":
        request = BacktestRequest(
            start_date=args.start,
            end_date=args.end,
            initial_capital_cny=args.capital,
            use_index_proxies=args.use_index_proxies,
        )
        _print(asyncio.run(service.run_backtest(request)))
        return
    raise RuntimeError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
