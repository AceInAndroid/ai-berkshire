import os
import sys
import tomllib
import types
from pathlib import Path

import pytest

from tradingagents_astock_mcp.config import Settings, default_worker_python
from tradingagents_astock_mcp.models import ResearchRequest
from tradingagents_astock_mcp.service import (
    ResearchService,
    SubprocessWorker,
    build_worker_environment,
)
from tradingagents_astock_mcp.worker import build_upstream_config


def test_config_is_deepcopied_env_overridden_and_run_isolated(monkeypatch, tmp_path):
    original = {
        "results_dir": "/shared/results",
        "data_cache_dir": "/shared/cache",
        "memory_log_path": "/shared/memory.md",
        "data_vendors": {"core_stock_apis": "wrong"},
        "llm_provider": "openai",
    }
    package = types.ModuleType("tradingagents")
    defaults = types.ModuleType("tradingagents.default_config")
    defaults.DEFAULT_CONFIG = original
    monkeypatch.setitem(sys.modules, "tradingagents", package)
    monkeypatch.setitem(sys.modules, "tradingagents.default_config", defaults)
    monkeypatch.setenv("TRADINGAGENTS_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("TRADINGAGENTS_DEEP_MODEL", "deep-model")
    monkeypatch.setenv("TRADINGAGENTS_QUICK_MODEL", "quick-model")

    request = ResearchRequest(ticker="600519", trade_date="2026-01-05", research_depth=3)
    config = build_upstream_config(tmp_path, request)

    assert original["results_dir"] == "/shared/results"
    assert original["data_vendors"]["core_stock_apis"] == "wrong"
    assert config["llm_provider"] == "anthropic"
    assert config["deep_think_llm"] == "deep-model"
    assert config["quick_think_llm"] == "quick-model"
    assert config["max_debate_rounds"] == config["max_risk_discuss_rounds"] == 3
    assert str(tmp_path.resolve()) in config["results_dir"]
    assert str(tmp_path.resolve()) in config["data_cache_dir"]
    assert str(tmp_path.resolve()) in config["memory_log_path"]
    assert config["data_vendors"]["core_stock_apis"] == "a_stock"


def test_worker_environment_excludes_unrelated_secrets_and_other_provider_keys():
    source = {
        "PATH": "/safe/bin",
        "PYTHONPATH": "/unsafe/module-shadowing",
        "PYTHONHOME": "/unsafe/python-home",
        "HOME": "/safe/home",
        "HTTPS_PROXY": "http://proxy.invalid",
        "SSL_CERT_FILE": "/safe/cert.pem",
        "TRADINGAGENTS_LLM_PROVIDER": "openai",
        "TRADINGAGENTS_DEEP_MODEL": "deep-model",
        "OPENAI_API_KEY": "selected-provider-key",
        "ANTHROPIC_API_KEY": "other-provider-key",
        "UNRELATED_SECRET": "must-not-leak",
        "TRADINGAGENTS_PRIVATE_SECRET": "must-not-leak-either",
        "EM_MIN_INTERVAL": "0.2",
    }
    worker_env = build_worker_environment(source)
    assert worker_env["OPENAI_API_KEY"] == "selected-provider-key"
    assert worker_env["EM_MIN_INTERVAL"] == "0.2"
    assert "ANTHROPIC_API_KEY" not in worker_env
    assert "PYTHONPATH" not in worker_env
    assert "PYTHONHOME" not in worker_env
    assert "UNRELATED_SECRET" not in worker_env
    assert "TRADINGAGENTS_PRIVATE_SECRET" not in worker_env


def test_worker_command_uses_configured_interpreter_and_trusted_entry(tmp_path):
    configured = tmp_path / "worker-venv" / "bin" / "python"
    worker = SubprocessWorker(configured, timeout_seconds=123)
    command = worker.command(tmp_path / "request.json", tmp_path / "result.json")
    assert command[0] == str(configured.absolute())
    assert command[1] == str(worker.entry_script)
    assert command[1].endswith("tradingagents_astock_mcp/worker_entry.py")
    assert "-m" not in command
    worker_env = worker.environment()
    assert worker_env["VIRTUAL_ENV"] == str(configured.absolute().parent.parent)
    assert worker_env["PATH"].split(os.pathsep)[0] == str(configured.absolute().parent)


@pytest.mark.skipif(os.name == "nt", reason="Unix virtualenv interpreter symlink behavior")
def test_worker_interpreter_symlink_is_not_resolved(monkeypatch, tmp_path):
    worker_python = tmp_path / ".local" / "share" / "tradingagents-astock" / "venv" / "bin" / "python"
    worker_python.parent.mkdir(parents=True)
    worker_python.symlink_to(sys.executable)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert default_worker_python() == worker_python.absolute()
    settings = Settings.from_env()
    worker = SubprocessWorker(settings.worker_python, timeout_seconds=123)
    assert worker.command(tmp_path / "request.json", tmp_path / "result.json")[0] == str(
        worker_python.absolute()
    )


def test_adapter_dependency_lock_excludes_upstream_runtime():
    service_root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((service_root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]
    assert any(dependency.startswith("mcp[cli]") for dependency in dependencies)
    assert any(dependency.startswith("pydantic") for dependency in dependencies)
    assert not any("tradingagents" in dependency.lower() for dependency in dependencies)

    lock = (service_root / "uv.lock").read_text(encoding="utf-8")
    assert 'name = "mcp"' in lock
    assert 'name = "tradingagents-astock"' not in lock


@pytest.mark.parametrize(
    ("installed", "provider", "credential", "expected_status", "upstream_status", "configured"),
    [
        ("0.2.21", "openai", None, "ok", "not_ready", False),
        ("0.2.21", "openai", "configured-key", "ok", "ready", True),
        ("0.2.20", "openai", "configured-key", "degraded", "version_mismatch", True),
        (None, "openai", "configured-key", "ok", "runtime_missing", True),
        ("0.2.21", "ollama", None, "ok", "ready", True),
    ],
)
def test_health_readiness_semantics(
    monkeypatch,
    tmp_path,
    installed,
    provider,
    credential,
    expected_status,
    upstream_status,
    configured,
):
    monkeypatch.setattr("tradingagents_astock_mcp.service.probe_worker_version", lambda _: installed)
    monkeypatch.setenv("TRADINGAGENTS_LLM_PROVIDER", provider)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    if credential:
        monkeypatch.setenv("OPENAI_API_KEY", credential)
    service = ResearchService(Settings(data_dir=tmp_path))
    health = service.health()
    assert health["status"] == expected_status
    assert health["modes"]["codex_native"] == {
        "status": "ready",
        "requires_external_llm_credentials": False,
        "execution_location": "codex_client",
    }
    assert health["modes"]["upstream_graph"]["status"] == upstream_status
    assert health["llm"]["configured"] is configured
