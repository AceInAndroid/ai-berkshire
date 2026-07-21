from __future__ import annotations

import os
from pathlib import Path

import yaml

from .models import PortfolioConfig


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_CONFIG_ROOT = PACKAGE_ROOT / "config"
PACKAGED_CONFIG_ROOT = Path(__file__).resolve().parent / "runtime_data"
CONFIG_ROOT = SOURCE_CONFIG_ROOT if SOURCE_CONFIG_ROOT.exists() else PACKAGED_CONFIG_ROOT
DEFAULT_CONFIG_PATH = CONFIG_ROOT / "portfolio.yaml"
DEFAULT_DB_PATH = PACKAGE_ROOT / "data" / "portfolio_monitor.db"
DEFAULT_ARTIFACTS_PATH = PACKAGE_ROOT / "artifacts"


def load_config(path: str | Path | None = None) -> PortfolioConfig:
    config_path = Path(path or os.getenv("PORTFOLIO_MONITOR_CONFIG", DEFAULT_CONFIG_PATH))
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    config = PortfolioConfig.model_validate(raw)
    validate_config(config)
    return config


def validate_config(config: PortfolioConfig) -> None:
    total_weight = sum(module.target_weight for module in config.modules.values())
    if abs(total_weight - 1.0) > 1e-9:
        raise ValueError(f"module target weights must total 1.0, got {total_weight}")
    total_amount = sum(module.target_amount_cny for module in config.modules.values())
    if abs(total_amount - config.initial_capital_cny) > 0.01:
        raise ValueError("module target amounts must equal initial capital")
    equity_weight = sum(config.modules[key].target_weight for key in ("dividend", "broad_market", "technology"))
    if abs(equity_weight - config.equity_weight_cap) > 1e-9:
        raise ValueError("equity module weights do not match equity cap")
    if config.modules["technology"].target_weight != config.technology_weight_cap:
        raise ValueError("technology target does not match technology cap")
    if len(config.instruments) != 15:
        raise ValueError(f"expected 15 monitored ETFs, got {len(config.instruments)}")
    stages = sorted(config.technology_stages, key=lambda item: item.stage)
    if [stage.stage for stage in stages] != [1, 2, 3, 4]:
        raise ValueError("technology stages must be 1..4")
    if stages[-1].cumulative_amount_cny != config.modules["technology"].target_amount_cny:
        raise ValueError("final technology stage must equal technology target")
    risk_assets = config.initial_authorization.get("risk_assets", {})
    if risk_assets.get("minimum_cny") != 105_000 or risk_assets.get("maximum_cny") != 125_000:
        raise ValueError("initial risk-asset authorization must remain 105k-125k")
    if config.initial_authorization.get("technology", {}).get("maximum_cny") != 25_000:
        raise ValueError("initial technology authorization must remain 25k")


def database_path(path: str | Path | None = None) -> Path:
    result = Path(path or os.getenv("PORTFOLIO_MONITOR_DB", DEFAULT_DB_PATH))
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


def artifacts_path(path: str | Path | None = None) -> Path:
    result = Path(path or os.getenv("PORTFOLIO_MONITOR_ARTIFACTS", DEFAULT_ARTIFACTS_PATH))
    result.mkdir(parents=True, exist_ok=True)
    return result
