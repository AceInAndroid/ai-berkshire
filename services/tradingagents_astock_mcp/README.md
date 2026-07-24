# TradingAgents-astock MCP adapter

This service exposes [TradingAgents-astock](https://github.com/simonlin1212/TradingAgents-astock)
as six read-only MCP tools. Codex-native research uses the active Codex model;
optional upstream research is asynchronous and every run gets a new
subprocess plus isolated result, cache, and memory directories. The service has
no broker integration and exposes no order, portfolio-write, shell, path, URL,
or credential input.

## Install in two isolated Python 3.12 environments

TradingAgents-astock and MCP intentionally cannot share an environment:
TradingAgents' `mootdx` dependency requires `httpx<0.26`, while MCP requires a
newer `httpx`. The adapter environment therefore contains only MCP/Pydantic and
the worker environment contains the pinned upstream runtime.

```bash
cd services/tradingagents_astock_mcp
uv sync --extra dev

uv venv ~/.local/share/tradingagents-astock/venv --python 3.12
uv pip install \
  --python ~/.local/share/tradingagents-astock/venv/bin/python \
  'git+https://github.com/simonlin1212/TradingAgents-astock.git@531176ac3161ca13db263495c18b8e0f09fc0eb2'
```

The commit above is release v0.2.21. On Windows, use the worker interpreter at
`%USERPROFILE%\.local\share\tradingagents-astock\venv\Scripts\python.exe`.
The worker does not install MCP, and the adapter does not install TradingAgents.

Configure the server process, never an MCP tool call:

```bash
export TRADINGAGENTS_LLM_PROVIDER=openai
export TRADINGAGENTS_DEEP_MODEL='your-deep-model'
export TRADINGAGENTS_QUICK_MODEL='your-quick-model'
export OPENAI_API_KEY='...'
export TRADINGAGENTS_MAX_CONCURRENT=1
export TRADINGAGENTS_MCP_DATA_DIR="$PWD/.runtime"
export TRADINGAGENTS_WORKER_PYTHON="$HOME/.local/share/tradingagents-astock/venv/bin/python"
```

Provider-native key variables such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`GOOGLE_API_KEY`, `MINIMAX_API_KEY`, or `DEEPSEEK_API_KEY` are inherited only by
the upstream worker. They are never accepted as tool arguments, persisted in
run JSON, or returned by health checks. Optional server-only settings are
`TRADINGAGENTS_BACKEND_URL`, `TRADINGAGENTS_OUTPUT_LANGUAGE`,
`TRADINGAGENTS_JOB_TIMEOUT_SECONDS`, `TRADINGAGENTS_MCP_HOST`, and
`TRADINGAGENTS_MCP_PORT`. `TRADINGAGENTS_WORKER_PYTHON` is server-only and is
never part of any MCP tool schema. If omitted, it uses the path shown above.

## Run and register

```bash
uv run tradingagents-astock-mcp serve --transport stdio
uv run tradingagents-astock-mcp serve --transport http  # http://127.0.0.1:8766/mcp
```

Example Codex/Claude-compatible stdio registration (use an absolute working
directory in clients that support `cwd`):

```json
{
  "mcpServers": {
    "tradingagents-astock": {
      "command": "uv",
      "args": ["run", "tradingagents-astock-mcp", "serve", "--transport", "stdio"],
      "cwd": "/absolute/path/to/ai-berkshire/services/tradingagents_astock_mcp",
      "env": {
        "TRADINGAGENTS_LLM_PROVIDER": "openai",
        "TRADINGAGENTS_DEEP_MODEL": "your-deep-model",
        "TRADINGAGENTS_QUICK_MODEL": "your-quick-model",
        "TRADINGAGENTS_WORKER_PYTHON": "/home/user/.local/share/tradingagents-astock/venv/bin/python",
        "TRADINGAGENTS_MAX_CONCURRENT": "1"
      }
    }
  }
}
```

Tools:

- `prepare_codex_native_research(...)` validates the request and returns a
  TradingAgents-style evidence/debate plan for the active Codex model. It needs
  no external LLM provider, model name, or API key and does not execute the
  upstream `TradingAgentsGraph`.
- `start_astock_research(ticker, trade_date, analysts, research_depth)` accepts
  a six-digit ticker or canonical exchange form such as `600519.SH`,
  `000001.SZ`, or `430047.BJ` (persisted upstream as six digits), a non-future
  ISO date, a non-empty subset of `market`,
  `social`, `news`, `fundamentals`, `policy`, `hot_money`, `lockup`, and depth
  `1`, `3`, or `5`.
- `get_astock_research_status(run_id)` polls lifecycle state.
- `get_astock_research_result(run_id)` returns only the versioned stable result.
- `list_astock_research_runs(limit)` lists persisted run metadata.
- `health_check()` reports separate `codex_native` and `upstream_graph`
  readiness without secret values. Missing provider credentials do not block
  Codex-native mode.

Run records survive restarts under `TRADINGAGENTS_MCP_DATA_DIR/runs`. Any job
left queued or running by a server restart is marked failed rather than silently
replayed. Inspect `worker.log` inside a run directory for local diagnostics; log
contents are intentionally not returned through MCP.

## License boundary

This adapter does not vendor upstream source. TradingAgents-astock is an
external Apache-2.0 dependency with its own copyright and notice obligations.
See [NOTICE](NOTICE) for the integration boundary.
