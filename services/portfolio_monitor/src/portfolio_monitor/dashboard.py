from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response

from .service import PortfolioMonitorService


ASSET_ROOT = Path(__file__).resolve().parent / "web"
ASSET_TYPES = {
    "dashboard.css": "text/css; charset=utf-8",
    "dashboard.js": "application/javascript; charset=utf-8",
}


class DashboardRoutes:
    """Read-only HTTP presentation layer for the local portfolio monitor."""

    def __init__(self, service: PortfolioMonitorService):
        self.service = service
        self.scan_lock = asyncio.Lock()

    async def dashboard(self, request: Request) -> Response:
        return FileResponse(ASSET_ROOT / "dashboard.html", media_type="text/html; charset=utf-8")

    async def asset(self, request: Request) -> Response:
        filename = request.path_params["filename"]
        media_type = ASSET_TYPES.get(filename)
        if not media_type:
            return JSONResponse({"error": "asset_not_found"}, status_code=404)
        return FileResponse(ASSET_ROOT / filename, media_type=media_type)

    async def dashboard_api(self, request: Request) -> Response:
        try:
            if self.service.database.latest_portfolio_snapshot():
                return JSONResponse(await self.service.get_dashboard(refresh=False))
            if self.scan_lock.locked():
                return JSONResponse(
                    {"status": "initializing", "refreshing": True, "retry_after_seconds": 2},
                    status_code=202,
                )
            async with self.scan_lock:
                return JSONResponse(await self.service.get_dashboard(refresh=False))
        except Exception as error:
            return self._error(error)

    async def refresh_api(self, request: Request) -> Response:
        if self.scan_lock.locked():
            cached: dict[str, Any] | None = None
            if self.service.database.latest_portfolio_snapshot():
                cached = await self.service.get_dashboard(refresh=False)
            return JSONResponse(
                {
                    "status": "refreshing",
                    "refreshing": True,
                    "retry_after_seconds": 2,
                    "dashboard": cached,
                },
                status_code=202,
            )
        try:
            async with self.scan_lock:
                dashboard = await self.service.get_dashboard(refresh=True)
            return JSONResponse({"status": "completed", "refreshing": False, "dashboard": dashboard})
        except Exception as error:
            return self._error(error)

    async def history_api(self, request: Request) -> Response:
        raw_limit = request.query_params.get("limit", "120")
        try:
            limit = int(raw_limit)
        except ValueError:
            return JSONResponse(
                {
                    "error": "invalid_limit",
                    "message": "limit must be an integer",
                    "data_as_of": datetime.now(UTC).isoformat(),
                    "retryable": False,
                },
                status_code=400,
            )
        return JSONResponse(
            {
                "data_as_of": datetime.now(UTC).isoformat(),
                "items": self.service.get_portfolio_history(limit),
            }
        )

    @staticmethod
    def _error(error: Exception) -> JSONResponse:
        return JSONResponse(
            {
                "error": type(error).__name__,
                "message": str(error),
                "data_as_of": datetime.now(UTC).isoformat(),
                "retryable": True,
            },
            status_code=503,
        )


def register_dashboard_routes(server: FastMCP, service: PortfolioMonitorService) -> DashboardRoutes:
    routes = DashboardRoutes(service)

    @server.custom_route("/", methods=["GET"], include_in_schema=False)
    async def root(request: Request) -> Response:
        return RedirectResponse("/dashboard", status_code=307)

    server.custom_route("/dashboard", methods=["GET"], include_in_schema=False)(routes.dashboard)
    server.custom_route(
        "/dashboard/assets/{filename}", methods=["GET"], include_in_schema=False
    )(routes.asset)
    server.custom_route("/api/dashboard", methods=["GET"], include_in_schema=False)(routes.dashboard_api)
    server.custom_route(
        "/api/dashboard/refresh", methods=["POST"], include_in_schema=False
    )(routes.refresh_api)
    server.custom_route(
        "/api/dashboard/history", methods=["GET"], include_in_schema=False
    )(routes.history_api)
    return routes
