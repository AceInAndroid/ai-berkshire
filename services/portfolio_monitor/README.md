# AI Berkshire Portfolio Monitor

A local, deterministic, read-only portfolio monitoring service for the 2026-07-20 AI Berkshire RMB 1,000,000 allocation policy.

## Capabilities

- Tracks 15 configured ETFs across cash, fixed income, gold, dividend, broad-market and technology Beta modules.
- Maintains a SQLite transaction ledger and calculates positions, P&L, allocation drift and drawdown.
- Evaluates deterministic buy, pause, reduce and rebalance rules, including the four-stage technology Beta state machine.
- Runs no-lookahead portfolio backtests with next-session execution.
- Exposes MCP tools, resources and prompts over stdio or Streamable HTTP.
- Serves a local read-only Chinese investment dashboard from the same HTTP process.
- Persists and deduplicates alerts, with optional OpenClaw Gateway webhook delivery.

This service **does not place, cancel, replace or finance trades**. It only records transactions that the user has already completed and provides research alerts.

## Setup

```bash
cd services/portfolio_monitor
uv sync --extra dev
uv run portfolio-monitor init-db
```

## Run a scan

```bash
uv run portfolio-monitor scan
```

For deterministic local replay:

```bash
PORTFOLIO_MONITOR_FIXTURE=tests/fixtures/market_20260720.json \
PORTFOLIO_MONITOR_DB=/tmp/portfolio-monitor-fixture.db \
uv run portfolio-monitor scan --no-alerts
```

## MCP servers

stdio:

```bash
uv run portfolio-monitor serve --transport stdio
```

Streamable HTTP (default `http://127.0.0.1:8765/mcp`):

```bash
uv run portfolio-monitor serve --transport http
```

Open the read-only dashboard at:

```text
http://127.0.0.1:8765/dashboard
```

The browser reads the latest SQLite snapshot every 60 seconds without requesting market providers. Only the **立即扫描** button performs a real provider refresh; that refresh persists the new snapshot but does not deliver OpenClaw alerts. The dashboard has no transaction, alert-management, risk-threshold or broker-operation endpoints.

A MCPorter/OpenClaw registration example is in `config/openclaw/mcporter.example.json`. Keep the service alive with the local process supervisor used by your OpenClaw deployment.

## Scheduler

```bash
OPENCLAW_WEBHOOK_URL=http://127.0.0.1:YOUR_GATEWAY_PORT/YOUR_ALERT_ENDPOINT \
uv run portfolio-monitor scheduler
```

The webhook schema is intentionally generic because OpenClaw Gateway deployments can expose different local endpoints. Failed deliveries remain pending in SQLite and are retried.

## Backtest

```bash
uv run portfolio-monitor backtest --start 2025-01-01 --end 2026-07-20
```

## Configuration and safety

- Runtime policy: `config/portfolio.yaml`
- SQLite migrations: `config/migrations/`
- Core risk thresholds cannot be modified through MCP.
- Optional Longbridge integration is restricted to an explicit read-only tool allowlist.
- Action alerts are blocked when price data is stale or when sources disagree beyond the configured tolerance.
