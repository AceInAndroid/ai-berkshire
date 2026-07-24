from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

UPSTREAM_VERSION = "0.2.21"
UPSTREAM_COMMIT = "531176ac3161ca13db263495c18b8e0f09fc0eb2"

PROVIDER_CREDENTIALS: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "google": ("GOOGLE_API_KEY",),
    "gemini": ("GOOGLE_API_KEY",),
    "minimax": ("MINIMAX_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "xai": ("XAI_API_KEY",),
    "qwen": ("DASHSCOPE_API_KEY",),
    "glm": ("ZHIPU_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "azure": ("AZURE_OPENAI_API_KEY",),
    "openai_compatible": ("OPENAI_COMPATIBLE_API_KEY", "OPENAI_API_KEY"),
}


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def default_worker_python() -> Path:
    worker_root = Path.home() / ".local" / "share" / "tradingagents-astock" / "venv"
    executable = worker_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    # Do not resolve the venv interpreter symlink: invoking its base-Python
    # target directly loses the virtual environment's sys.prefix and packages.
    return executable.absolute()


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    worker_python: Path = field(default_factory=default_worker_python)
    max_concurrent: int = 1
    job_timeout_seconds: int = 7_200
    host: str = "127.0.0.1"
    port: int = 8766

    @classmethod
    def from_env(cls) -> "Settings":
        default_dir = Path.home() / ".local" / "state" / "ai-berkshire" / "tradingagents-astock-mcp"
        data_dir = Path(os.getenv("TRADINGAGENTS_MCP_DATA_DIR", str(default_dir))).expanduser().resolve()
        worker_python = Path(
            os.getenv("TRADINGAGENTS_WORKER_PYTHON", str(default_worker_python()))
        ).expanduser().absolute()
        return cls(
            data_dir=data_dir,
            worker_python=worker_python,
            max_concurrent=_bounded_int("TRADINGAGENTS_MAX_CONCURRENT", 1, 1, 8),
            job_timeout_seconds=_bounded_int("TRADINGAGENTS_JOB_TIMEOUT_SECONDS", 7_200, 60, 86_400),
            host=os.getenv("TRADINGAGENTS_MCP_HOST", "127.0.0.1"),
            port=_bounded_int("TRADINGAGENTS_MCP_PORT", 8766, 1, 65_535),
        )
