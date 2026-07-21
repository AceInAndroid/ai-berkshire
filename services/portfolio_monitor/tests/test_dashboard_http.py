import json
from pathlib import Path

import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

from portfolio_monitor.dashboard import DashboardRoutes
from portfolio_monitor.mcp_server import create_mcp
from portfolio_monitor.providers import FixtureProvider, ProviderRegistry
from portfolio_monitor.service import PortfolioMonitorService


@pytest.fixture
def dashboard_service(config, database):
    fixture = Path(__file__).parent / "fixtures" / "market_20260720.json"
    return PortfolioMonitorService(
        config=config,
        database=database,
        providers=ProviderRegistry(FixtureProvider(fixture)),
    )


@pytest.fixture
def dashboard_client(dashboard_service):
    app = create_mcp(dashboard_service).streamable_http_app()
    with TestClient(app) as client:
        yield client


def test_dashboard_pages_assets_and_root_redirect(dashboard_client):
    root = dashboard_client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/dashboard"

    html = dashboard_client.get("/dashboard")
    css = dashboard_client.get("/dashboard/assets/dashboard.css")
    js = dashboard_client.get("/dashboard/assets/dashboard.js")
    missing = dashboard_client.get("/dashboard/assets/unknown.js")

    assert html.status_code == 200
    assert "text/html" in html.headers["content-type"]
    assert "组合监控驾驶舱" in html.text
    assert css.status_code == 200 and "text/css" in css.headers["content-type"]
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    assert "requestJson(\"/api/dashboard\"" in js.text
    assert missing.status_code == 404


def test_api_initializes_database_then_reads_cached_snapshot(dashboard_client, dashboard_service, monkeypatch):
    initial = dashboard_client.get("/api/dashboard")
    assert initial.status_code == 200
    payload = initial.json()
    assert payload["market_regime"]["regime"] == "STABILIZING"
    assert len(payload["indicators"]) == 15

    async def provider_call_must_not_run(*_args, **_kwargs):
        raise AssertionError("automatic dashboard polling must remain cache-only")

    monkeypatch.setattr(dashboard_service.providers, "quotes", provider_call_must_not_run)
    cached = dashboard_client.get("/api/dashboard")
    assert cached.status_code == 200
    assert cached.json()["data_as_of"] == payload["data_as_of"]


def test_manual_refresh_persists_without_delivering_alerts(dashboard_client, dashboard_service, monkeypatch):
    dashboard_client.get("/api/dashboard")

    async def alerts_must_not_be_delivered(*_args, **_kwargs):
        raise AssertionError("dashboard refresh must use send_alerts=False")

    monkeypatch.setattr(
        dashboard_service.alerts,
        "process_recommendations",
        alerts_must_not_be_delivered,
    )
    refreshed = dashboard_client.post("/api/dashboard/refresh")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "completed"
    assert refreshed.json()["dashboard"]["portfolio_history"]


def test_history_validation_and_read_only_route_surface(dashboard_client):
    invalid = dashboard_client.get("/api/dashboard/history?limit=abc")
    assert invalid.status_code == 400
    assert invalid.json()["retryable"] is False
    assert "data_as_of" in invalid.json()

    dashboard_client.get("/api/dashboard")
    history = dashboard_client.get("/api/dashboard/history?limit=1")
    assert history.status_code == 200
    assert len(history.json()["items"]) == 1

    forbidden_paths = (
        "/api/transactions",
        "/api/alerts/acknowledge",
        "/api/alerts/snooze",
        "/api/risk-thresholds",
        "/api/orders",
        "/api/broker",
    )
    for path in forbidden_paths:
        assert dashboard_client.post(path).status_code == 404


@pytest.mark.asyncio
async def test_concurrent_refresh_returns_current_task_state(dashboard_service):
    routes = DashboardRoutes(dashboard_service)
    request = Request({"type": "http", "method": "POST", "path": "/api/dashboard/refresh", "headers": []})

    await routes.scan_lock.acquire()
    try:
        response = await routes.refresh_api(request)
    finally:
        routes.scan_lock.release()

    assert response.status_code == 202
    payload = json.loads(response.body)
    assert payload["status"] == "refreshing"
    assert payload["retry_after_seconds"] == 2


@pytest.mark.asyncio
async def test_dashboard_errors_use_structured_retryable_json(dashboard_service, monkeypatch):
    routes = DashboardRoutes(dashboard_service)
    request = Request({"type": "http", "method": "GET", "path": "/api/dashboard", "headers": []})

    async def fail(*_args, **_kwargs):
        raise RuntimeError("provider offline")

    monkeypatch.setattr(dashboard_service, "get_dashboard", fail)
    response = await routes.dashboard_api(request)
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["error"] == "RuntimeError"
    assert payload["retryable"] is True
    assert "data_as_of" in payload
