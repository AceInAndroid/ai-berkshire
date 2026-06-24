from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from openclaw.profile_validators import (
    validate_ai_bottleneck_research,
    validate_commodity_real_assets_research,
    validate_common_envelope,
    validate_earnings_season_research,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "openclaw"
XIAOMI_REPORT = REPO_ROOT / "reports" / "小米" / "小米-research-20260624.md"
OPENCLAW_WORLD_MODEL = Path("/Users/bingzhang/clawd/myclaw-repo/data/world_model")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_exporter():
    path = REPO_ROOT / "tools" / "openclaw_export.py"
    spec = importlib.util.spec_from_file_location("openclaw_export", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OpenClawExportTest(unittest.TestCase):
    def test_openclaw_profile_fixtures_validate(self) -> None:
        ai = _load_json(FIXTURE_DIR / "ai_bottleneck_research_latest.json")
        commodity = _load_json(FIXTURE_DIR / "commodity_real_assets_research_latest.json")
        earnings = _load_json(FIXTURE_DIR / "earnings_season_research_latest.json")

        self.assertEqual(validate_ai_bottleneck_research(ai).status, "healthy")
        self.assertEqual(validate_commodity_real_assets_research(commodity).status, "healthy")
        self.assertEqual(validate_earnings_season_research(earnings).status, "healthy")

    def test_ai_bottleneck_single_company_payload_fails_closed(self) -> None:
        payload = {
            "generated_at": "2026-06-24T00:00:00+08:00",
            "status": "healthy",
            "coverage": {
                "symbols_total": 1,
                "symbols_with_order_evidence": 1,
                "symbols_with_margin_cashflow": 1,
                "source_count": 1,
            },
            "market_thesis": "single company report",
            "bottleneck_lanes": [],
            "top_targets": [{"symbol": "1810.HK", "evidence": {}}],
            "watch_targets": [],
            "avoid_targets": [],
            "health_notes": [],
        }

        result = validate_ai_bottleneck_research(payload)

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "critical")
        self.assertIn("coverage.symbols_total_lt_20", result.errors)

    def test_earnings_without_longbridge_is_degraded(self) -> None:
        payload = _load_json(FIXTURE_DIR / "earnings_season_research_latest.json")
        payload["coverage"]["source_counts"] = {"yfinance_ok": 20}
        for row in payload.get("analyzed_targets", []):
            row["evidence_provenance"] = [{"source": "yfinance"}]

        result = validate_earnings_season_research(payload)

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "degraded")
        self.assertIn("longbridge_provenance_missing", result.warnings)

    def test_common_envelope_requires_ai_berkshire_source(self) -> None:
        result = validate_common_envelope({
            "schema_version": "v1",
            "generated_at": "2026-06-24T00:00:00+08:00",
            "source_repo": "other",
            "source_report": "report.md",
            "artifact_type": "company_research",
            "status": "healthy",
            "confidence": "high",
            "market_thesis": "test",
            "validation_summary": {},
        })

        self.assertFalse(result.ok)
        self.assertIn("source_repo_must_be_ai-berkshire", result.errors)

    def test_xiaomi_export_writes_to_default_style_output(self) -> None:
        exporter = _load_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            args = exporter.build_parser().parse_args([
                "--report",
                str(XIAOMI_REPORT),
                "--skill",
                "investment-research",
                "--symbol",
                "1810.HK",
                "--market",
                "HK",
                "--company-name",
                "小米集团",
                "--research-type",
                "company_research",
                "--output-dir",
                tmp,
            ])

            payload = exporter.export_report(args)

            self.assertEqual(payload["source_repo"], "ai-berkshire")
            self.assertEqual(payload["symbol"], "1810.HK")
            self.assertTrue(Path(payload["json_path"]).exists())
            self.assertTrue(Path(payload["latest_path"]).exists())
            self.assertNotIn(str(OPENCLAW_WORLD_MODEL), payload["json_path"])

    def test_xiaomi_earnings_profile_fails_closed_without_longbridge(self) -> None:
        exporter = _load_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            args = exporter.build_parser().parse_args([
                "--report",
                str(XIAOMI_REPORT),
                "--skill",
                "investment-research",
                "--symbol",
                "1810.HK",
                "--market",
                "HK",
                "--company-name",
                "小米集团",
                "--research-type",
                "earnings_review",
                "--target-profile",
                "earnings_season_research",
                "--output-dir",
                tmp,
            ])

            payload = exporter.export_report(args)

            self.assertEqual(payload["status"], "critical")
            self.assertIn("profile_validation", payload)
            self.assertIn("longbridge_provenance_missing", payload["degrade_reasons"])

    def test_phase_one_rejects_openclaw_world_model_output(self) -> None:
        exporter = _load_exporter()

        with self.assertRaises(SystemExit):
            exporter._ensure_safe_output_dir(str(OPENCLAW_WORLD_MODEL / "ai_bottleneck_research"))


if __name__ == "__main__":
    unittest.main()
