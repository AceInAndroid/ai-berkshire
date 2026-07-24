from __future__ import annotations

import asyncio
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .config import PROVIDER_CREDENTIALS, Settings, UPSTREAM_VERSION
from .models import ResearchRequest, RunRecord
from .store import RunStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summary(record: RunRecord) -> dict[str, Any]:
    return record.model_dump(exclude={"result"})


class WorkerRunner(Protocol):
    async def run(self, request: ResearchRequest, run_dir: Path) -> dict[str, Any]: ...


_BASE_WORKER_ENV = {
    "PATH",
    "VIRTUAL_ENV",
    "HOME",
    "TMPDIR",
    "TMP",
    "TEMP",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "EM_MIN_INTERVAL",
}
_WORKER_CONFIG_ENV = {
    "TRADINGAGENTS_LLM_PROVIDER",
    "TRADINGAGENTS_DEEP_MODEL",
    "TRADINGAGENTS_QUICK_MODEL",
    "TRADINGAGENTS_BACKEND_URL",
    "TRADINGAGENTS_OUTPUT_LANGUAGE",
}


def build_worker_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Return the minimal environment required by the selected upstream provider."""
    parent = os.environ if source is None else source
    provider = parent.get("TRADINGAGENTS_LLM_PROVIDER", "openai").strip().lower()
    allowed = _BASE_WORKER_ENV | _WORKER_CONFIG_ENV | set(PROVIDER_CREDENTIALS.get(provider, ()))
    return {name: parent[name] for name in allowed if name in parent}


def probe_worker_version(worker_python: Path, timeout_seconds: float = 5.0) -> str | None:
    """Read package metadata from the isolated worker without importing it here."""
    command = (
        str(worker_python),
        "-c",
        "import importlib.metadata as m; print(m.version('tradingagents-astock'))",
    )
    probe_env = {name: os.environ[name] for name in _BASE_WORKER_ENV if name in os.environ}
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=probe_env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    version = completed.stdout.strip()
    return version or None


class SubprocessWorker:
    def __init__(self, worker_python: Path, timeout_seconds: int):
        # Preserve virtualenv interpreter symlinks for the same reason as
        # config.default_worker_python().
        self.worker_python = worker_python.expanduser().absolute()
        self.timeout_seconds = timeout_seconds
        self.entry_script = Path(__file__).with_name("worker_entry.py").resolve()

    def command(self, request_path: Path, result_path: Path) -> tuple[str, ...]:
        return (
            str(self.worker_python),
            str(self.entry_script),
            "--request",
            str(request_path),
            "--result",
            str(result_path),
        )

    def environment(self) -> dict[str, str]:
        environment = build_worker_environment()
        worker_bin = self.worker_python.parent
        environment["VIRTUAL_ENV"] = str(worker_bin.parent)
        existing_path = environment.get("PATH")
        environment["PATH"] = (
            str(worker_bin) if not existing_path else f"{worker_bin}{os.pathsep}{existing_path}"
        )
        return environment

    async def run(self, request: ResearchRequest, run_dir: Path) -> dict[str, Any]:
        request_path = run_dir / "worker-request.json"
        result_path = run_dir / "worker-result.json"
        log_path = run_dir / "worker.log"
        request_path.write_text(request.model_dump_json(indent=2) + "\n", encoding="utf-8")
        with log_path.open("ab") as log:
            process = await asyncio.create_subprocess_exec(
                *self.command(request_path, result_path),
                cwd=run_dir,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                env=self.environment(),
            )
            try:
                return_code = await asyncio.wait_for(process.wait(), timeout=self.timeout_seconds)
            except asyncio.CancelledError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=10)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                raise
            except TimeoutError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=10)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                raise RuntimeError("analysis worker timed out") from None
        if return_code != 0:
            raise RuntimeError(f"analysis worker exited with code {return_code}")
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise RuntimeError("analysis worker returned no valid result") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise RuntimeError("analysis worker returned an unsupported result")
        return payload


class ResearchService:
    def __init__(self, settings: Settings | None = None, worker: WorkerRunner | None = None):
        self.settings = settings or Settings.from_env()
        self.store = RunStore(self.settings.data_dir / "runs")
        self.recovered_runs = self.store.recover_interrupted()
        self.worker = worker or SubprocessWorker(
            self.settings.worker_python,
            self.settings.job_timeout_seconds,
        )
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent)
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(
        self,
        ticker: str,
        trade_date: str,
        analysts: list[str] | None = None,
        research_depth: int = 1,
    ) -> dict[str, Any]:
        raw: dict[str, Any] = {
            "ticker": ticker,
            "trade_date": trade_date,
            "research_depth": research_depth,
        }
        if analysts is not None:
            raw["analysts"] = analysts
        request = ResearchRequest.model_validate(raw)
        run_id = uuid.uuid4().hex
        record = RunRecord(
            run_id=run_id,
            status="queued",
            request=request,
            created_at=_now(),
        )
        self.store.create(record)
        task = asyncio.create_task(self._execute(run_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return _summary(record)

    def prepare_codex_native(
        self,
        ticker: str,
        trade_date: str,
        analysts: list[str] | None = None,
        research_depth: int = 1,
    ) -> dict[str, Any]:
        """Return a validated client-side plan that uses the active Codex model."""
        raw: dict[str, Any] = {
            "ticker": ticker,
            "trade_date": trade_date,
            "research_depth": research_depth,
        }
        if analysts is not None:
            raw["analysts"] = analysts
        request = ResearchRequest.model_validate(raw)
        return {
            "schema_version": 1,
            "execution_mode": "codex_native",
            "requires_external_llm_credentials": False,
            "upstream_graph_executed": False,
            "request": request.model_dump(),
            "workflow": {
                "evidence_roles": [
                    {
                        "name": "fundamentals",
                        "focus": "business quality, financial statements, valuation inputs, and source gaps",
                    },
                    {
                        "name": "market_flow",
                        "focus": "price action, liquidity, momentum, fund flow, margin, and block trades",
                    },
                    {
                        "name": "news_policy_events",
                        "focus": "news, sentiment, policy, hot money, lockups, catalysts, and event risk",
                    },
                ],
                "debate_roles": ["bull", "bear", "risk_reviewer"],
                "final_authority": "ai_berkshire_lead",
            },
            "disclosure": (
                "TradingAgents-astock role topology is adapted for Codex client orchestration; "
                "the original upstream TradingAgentsGraph is not executed in this mode."
            ),
        }

    async def _execute(self, run_id: str) -> None:
        async with self._semaphore:
            record = self.store.get(run_id)
            record.status = "running"
            record.started_at = _now()
            self.store.save(record)
            try:
                record.result = await self.worker.run(record.request, self.store.run_dir(run_id))
            except asyncio.CancelledError:
                record.status = "failed"
                record.completed_at = _now()
                record.error = {"code": "server_stopping", "message": "Run interrupted by server shutdown"}
                self.store.save(record)
                raise
            except Exception as exc:
                record.status = "failed"
                record.completed_at = _now()
                record.error = {"code": "worker_failed", "message": str(exc)[:500]}
                self.store.save(record)
            else:
                record.status = "completed"
                record.completed_at = _now()
                self.store.save(record)

    def status(self, run_id: str) -> dict[str, Any]:
        return _summary(self.store.get(run_id))

    def result(self, run_id: str) -> dict[str, Any]:
        record = self.store.get(run_id)
        if record.status != "completed":
            raise ValueError(f"research run is {record.status}, not completed")
        return {"run_id": run_id, "status": record.status, "result": record.result}

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return [_summary(record) for record in self.store.list(limit=limit)]

    def health(self) -> dict[str, Any]:
        provider = os.getenv("TRADINGAGENTS_LLM_PROVIDER", "openai").strip().lower()
        key_names = PROVIDER_CREDENTIALS.get(provider, ())
        installed = probe_worker_version(self.settings.worker_python)
        configured = provider == "ollama" or any(os.getenv(name) for name in key_names)
        if installed is None:
            upstream_status = "runtime_missing"
        elif installed != UPSTREAM_VERSION:
            upstream_status = "version_mismatch"
        elif not configured:
            upstream_status = "not_ready"
        else:
            upstream_status = "ready"
        status = "ok" if installed in {None, UPSTREAM_VERSION} else "degraded"
        return {
            "status": status,
            "read_only": True,
            "broker_connected": False,
            "max_concurrent": self.settings.max_concurrent,
            "active_jobs": sum(not task.done() for task in self._tasks),
            "modes": {
                "codex_native": {
                    "status": "ready",
                    "requires_external_llm_credentials": False,
                    "execution_location": "codex_client",
                },
                "upstream_graph": {
                    "status": upstream_status,
                    "requires_external_llm_credentials": True,
                    "execution_location": "isolated_worker",
                },
            },
            "upstream": {
                "status": upstream_status,
                "expected_version": UPSTREAM_VERSION,
                "installed_version": installed,
            },
            "llm": {
                "provider": provider,
                "configured": configured,
                "required_for": "upstream_graph_only",
            },
            "recovered_interrupted_runs": self.recovered_runs,
        }

    async def close(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
