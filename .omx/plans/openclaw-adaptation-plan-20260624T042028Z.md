# Ralplan: Adapt AI Berkshire For OpenClaw

Status: ralplan consensus approved

## Requirements Summary

Adapt AI Berkshire so Codex-generated investment research can be consumed by OpenClaw without creating a second investment committee, scheduler, or health system.

The target integration is an artifact contract: AI Berkshire keeps producing human-readable Chinese research reports, and also emits machine-readable OpenClaw sidecar/export JSON with enough metadata for OpenClaw to decide freshness, confidence, degradation, market, symbol, thesis impact, source quality, and validation status.

## RALPLAN-DR Summary

Principles:
- Preserve OpenClaw authority: OpenClaw remains the scheduler, health checker, daily committee, and Telegram delivery owner.
- Make AI Berkshire outputs structured, auditable, and explicit about uncertainty.
- Prefer adapter/export contracts over direct mutation of OpenClaw runtime state.
- Keep phase 1 contained in AI Berkshire because the OpenClaw worktree is dirty.
- Never convert weak or stale evidence into a healthy OpenClaw signal.

Decision drivers:
- OpenClaw already has ingestion slots at `data/world_model/*_research/latest.json` and consumes them in `daily_ic`.
- AI Berkshire already has Codex skills and validation tools, but its outputs are mostly Markdown and not reliably machine-readable.
- The safest bridge is schema-first export plus validation, then optional OpenClaw consumer changes after a clean branch is available.

Viable options:
- Option A: AI Berkshire exporter + schema + docs first.
  - Pros: small blast radius, works with dirty OpenClaw repo, testable locally, does not duplicate scheduler.
  - Cons: OpenClaw will need a later copy/import step before full automation.
- Option B: direct OpenClaw integration now.
  - Pros: fastest path to end-to-end OpenClaw consumption.
  - Cons: higher conflict risk because OpenClaw is dirty; easy to entangle AI Berkshire with runtime state.
- Option C: keep Markdown only and teach OpenClaw to parse reports.
  - Pros: fewer AI Berkshire changes.
  - Cons: brittle parsing, weak health semantics, harder to test, likely to hide degradation.

Chosen direction: Option A for phase 1, with an explicit phase 2 OpenClaw consumer only after the exporter contract is stable.

## Evidence Anchors

- AI Berkshire Codex skills live under `.codex/skills`; `docs/codex-usage.md` documents invocation and validation commands.
- OpenClaw daily committee reads research latest files at `/Users/bingzhang/clawd/myclaw-repo/scripts/jobs/daily_investment_committee.py:61`.
- OpenClaw daily committee loads these payloads with `_latest_*_research()` at `/Users/bingzhang/clawd/myclaw-repo/scripts/jobs/daily_investment_committee.py:230`.
- Degraded daily committee payloads preserve `degraded`, `degrade_reason`, `input_assertion`, and research payloads at `/Users/bingzhang/clawd/myclaw-repo/scripts/jobs/daily_investment_committee.py:367`.
- Normal daily committee payloads include `input_assertion`, `ai_bottleneck_research`, `commodity_real_assets_research`, and `earnings_season_research` at `/Users/bingzhang/clawd/myclaw-repo/scripts/jobs/daily_investment_committee.py:4228`.
- OpenClaw scheduler runs research products before committee in `committee` stage at `/Users/bingzhang/clawd/myclaw-repo/scripts/assistant_mode_scheduler.py:729`.
- OpenClaw briefing consumes latest `daily_ic` and preserves degraded state at `/Users/bingzhang/clawd/myclaw-repo/scripts/daily_operating_briefing.py:241`.
- OpenClaw health checks already inspect AI bottleneck research latest JSON at `/Users/bingzhang/clawd/myclaw-repo/scripts/data_source_health_check.py:563`.

## Proposed Contract

Add an AI Berkshire OpenClaw export contract with three layers:

1. Report sidecar schema, next to each AI Berkshire report:
   - `schema_version`
   - `generated_at`
   - `report_path`
   - `skill`
   - `company_name`
   - `symbol`
   - `market`
   - `topic`
   - `research_type`
   - `status`: `healthy | degraded | critical`
   - `confidence`: `low | medium | high`
   - `degrade_reasons`
   - `source_health`
   - `validation_summary`
   - `thesis_verdict`
   - `one_to_four_week_view`
   - `market_thesis`
   - `top_targets`
   - `watch_targets`
   - `avoid_targets`
   - `evidence_gaps`
   - `openclaw_targets`: candidate OpenClaw product types, for example `company_research`, `earnings_season_research`, `ai_bottleneck_research`.

2. Export bundle schema for OpenClaw import:
   - `generated_at`
   - `source_repo`
   - `source_report`
   - `artifact_type`
   - `status`
   - `coverage`
   - `market_thesis`
   - `report_sections`
   - `top_targets`
   - `watch_targets`
   - `avoid_targets`
   - `source_health`
   - `json_path`
   - `latest_path`

The export bundle should be a common envelope, not the whole contract. It must be marked as `source_repo: ai-berkshire` and should never overwrite OpenClaw files unless a later command explicitly asks for that.

3. `openclaw_target_profiles`, because OpenClaw does not consume a single generic JSON shape.

| Target profile | Required fields | Status / downgrade rules | Forbidden behavior |
| --- | --- | --- | --- |
| `ai_bottleneck_research` | `generated_at`, `status`, `coverage.symbols_total`, `coverage.symbols_with_order_evidence`, `coverage.symbols_with_margin_cashflow`, `coverage.source_count`, `market_thesis`, `bottleneck_lanes`, `top_targets`, `watch_targets`, `avoid_targets`, `health_notes` | `critical` if `coverage.symbols_total < 20`; `degraded` if `coverage.source_count < 3`; `degraded` if `len(top_targets) < 3`; `degraded` if any of the first five `top_targets` lacks both demand evidence (`evidence.orders` or `evidence.customers`) and financial-quality evidence (`evidence.margin` or `evidence.cashflow`) | Do not mark a single-company report as healthy AI bottleneck research |
| `commodity_real_assets_research` | `generated_at`, `status`, `coverage.tracked_symbols`, `coverage.data_ok`, `coverage.missing_symbols`, `market_thesis`, `macro_view`, `asset_metrics`, `focus_targets`, `top_targets`, `watch_targets`, `health_notes` | `critical` if `coverage.data_ok < 8`; `degraded` if `coverage.missing_symbols` is non-empty; `degraded` if `macro_view.regime` is empty; `degraded` if `len(focus_targets) < 3`; `degraded` if `asset_metrics` lacks copper proxy coverage such as `HG=F` or `CPER` when the payload claims copper exposure | Do not map ordinary company research into this profile unless the report actually covers copper/real-assets basket evidence |
| `earnings_season_research` | `generated_at`, `status`, `coverage.universe_size`, `coverage.analyzed_count`, `coverage.source_counts`, `coverage.evidence_rows`, `market_thesis`, `selection_reason`, `source_health`, `analyzed_targets`, `top_targets`, `watch_targets`, `avoid_targets`, `evidence_gaps`, `report_sections` | `critical` if `coverage.evidence_rows < 4`; `critical` if required `report_sections` titles are missing; `degraded` if `source_health.status == degraded`; `degraded` if no Longbridge filing, financial-report, consensus, or calendar provenance appears in `coverage.source_counts` or `analyzed_targets[*].evidence_provenance`; `degraded` if only yfinance/narrative evidence exists | Do not present yfinance-only evidence as primary earnings evidence; Longbridge provenance must stay explicit |

The exporter should therefore implement a common envelope plus product-profile validators. A report may emit only the profiles it can honestly satisfy. For example, the Xiaomi company report can emit `company_research` and perhaps `earnings_season_research` if the required earnings provenance is present, but it should not emit `ai_bottleneck_research` unless it covers a broad AI bottleneck universe.

## Implementation Plan

1. Add OpenClaw export documentation in AI Berkshire.
   - Extend `docs/codex-usage.md` or add `docs/openclaw-adapter.md`.
   - Document `/Users/bingzhang/clawd/myclaw-repo` as the single OpenClaw authority and mention that `/Users/bingzhang/Documents/myclaw` is a symlink.
   - Document that phase 1 writes export files only under AI Berkshire.

2. Add schema validators and examples.
   - Use a stdlib Python validator as source of truth at `openclaw/profile_validators.py`; do not add a JSON Schema dependency.
   - Add JSON example documents under `openclaw/examples/` for the common envelope and each target profile.
   - Add `openclaw_target_profiles` definitions for `ai_bottleneck_research`, `commodity_real_assets_research`, and `earnings_season_research`.
   - Add one sample export derived from the existing Xiaomi report at `reports/小米/小米-research-20260624.md`.
   - Default exporter output should be `data/openclaw_exports/`; avoid writing sidecars into report directories by default.

3. Add an exporter CLI.
   - Suggested path: `tools/openclaw_export.py`.
   - Inputs: `--report`, `--skill`, `--symbol`, `--market`, `--company-name`, `--research-type`, optional `--target-profile`, optional `--output-dir`.
   - Outputs: sidecar JSON next to the report or under `data/openclaw_exports/`, plus a normalized export bundle and profile validation result.
   - Derive `status` from required metadata, report audit output, validation summary, and explicit evidence gaps.
   - Fail closed: if a requested target profile lacks required fields, emit `status=degraded` or `critical` with `profile_errors` instead of fabricating fields.
   - Treat Longbridge provenance as a hard earnings-profile downgrade rule: a Xiaomi company report may produce a company-research export, but must not pass as healthy `earnings_season_research` only because fields were syntactically filled.
   - Use stdlib only unless a dependency already exists.

4. Update Codex skill instructions to require sidecar/export metadata when OpenClaw adaptation is requested.
   - Start with `.codex/skills/investment-research/SKILL.md`, `.codex/skills/earnings-review/SKILL.md`, `.codex/skills/news-pulse/SKILL.md`, and `.codex/skills/bottleneck-hunter/SKILL.md`.
   - Require explicit machine-readable fields in report front matter or a sidecar JSON.
   - Require degraded status when key evidence is missing, stale, single-source, or unaudited.

5. Add tests and validation commands.
   - Unit test exporter schema validation, status mapping, and all product-profile validators.
   - Smoke test against an existing Xiaomi report.
   - Add tests in `tests/test_openclaw_export.py`.
   - Add fixture compatibility checks under `tests/fixtures/openclaw/` using copied OpenClaw-style sample payloads:
     - `tests/fixtures/openclaw/ai_bottleneck_research_latest.json`
     - `tests/fixtures/openclaw/commodity_real_assets_research_latest.json`
     - `tests/fixtures/openclaw/earnings_season_research_latest.json`
   - Prefer deriving those fixtures from current OpenClaw sample files:
     - `/Users/bingzhang/clawd/myclaw-repo/data/world_model/ai_bottleneck_research/latest.json`
     - `/Users/bingzhang/clawd/myclaw-repo/data/world_model/commodity_real_assets_research/latest.json`
     - `/Users/bingzhang/clawd/myclaw-repo/data/world_model/earnings_season_research/latest.json`
   - Ensure generated JSON has fields OpenClaw can consume without Markdown parsing.

6. Prepare phase 2 OpenClaw handoff, without editing OpenClaw yet.
   - Define exactly where an OpenClaw importer would read AI Berkshire exports.
   - Candidate later targets:
     - `scripts/assistant_mode_scheduler.py` import step before `ai_bottleneck_research` or `earnings_season_research`.
     - `scripts/data_source_health_check.py` health entry for external AI Berkshire research freshness.
     - `scripts/jobs/daily_investment_committee.py` optional external research block.
   - Make the importer OpenClaw-owned: AI Berkshire can write artifacts, but OpenClaw must decide import, health status, daily committee inclusion, and degraded state.
   - Require a clean OpenClaw branch before making those changes.

## Acceptance Criteria

- A developer can run a single AI Berkshire command that converts an existing report into a JSON sidecar/export bundle.
- The export JSON includes `generated_at`, `status`, `confidence`, `source_health`, `validation_summary`, `market_thesis`, and report path.
- Requested OpenClaw target profiles are validated against product-specific required fields and downgrade rules.
- A single-company report cannot accidentally pass as healthy `ai_bottleneck_research` or `commodity_real_assets_research`.
- Earnings exports preserve Longbridge provenance separately from yfinance or narrative evidence.
- Missing or weak validation results in `status=degraded` or `status=critical`, not `healthy`.
- No command writes into `/Users/bingzhang/clawd/myclaw-repo/data/world_model` by default.
- Documentation explains the OpenClaw authority path and phase 1/phase 2 boundary.
- Updated skill instructions tell Codex when and how to produce OpenClaw-compatible metadata.
- Tests pass for schema validation and a Xiaomi sample export.
- `tests/test_openclaw_export.py` covers common envelope validation, three target-profile validators, degradation thresholds, Xiaomi export smoke test, and OpenClaw no-mutation behavior.

## Risks And Mitigations

- Risk: OpenClaw schema drift.
  - Mitigation: keep exporter schema close to current `*_research/latest.json` shape and include `schema_version`.
- Risk: Markdown parsing creates false confidence.
  - Mitigation: prefer explicit sidecar fields and only derive weak defaults from Markdown.
- Risk: OpenClaw dirty repo makes direct integration unsafe.
  - Mitigation: phase 1 stays in AI Berkshire; phase 2 starts only on clean branch/worktree; no-mutation checks compare OpenClaw `git status --short` before and after exporter tests.
- Risk: users mistake AI Berkshire research for OpenClaw-verified daily committee output.
  - Mitigation: include `source_repo`, `validation_summary`, `status`, and explicit `degrade_reasons`.
- Risk: Longbridge source priority is bypassed for earnings.
  - Mitigation: AI Berkshire earnings export is supplemental unless it contains primary-source metadata; OpenClaw remains authority for Longbridge filing/financial-report/consensus/calendar evidence.

## Verification Steps

- `python3 tools/openclaw_export.py --report reports/小米/小米-research-20260624.md --skill investment-research --symbol 1810.HK --market HK --company-name 小米集团 --research-type company_research --output-dir data/openclaw_exports`
- `python3 tools/openclaw_export.py --report reports/小米/小米-research-20260624.md --skill investment-research --symbol 1810.HK --market HK --company-name 小米集团 --research-type earnings_review --target-profile earnings_season_research --output-dir data/openclaw_exports`
- `python3 -m unittest tests/test_openclaw_export.py`
- `python3 tools/report_audit.py extract --report reports/小米/小米-research-20260624.md --dry-run`
- Before exporter tests: `git -C /Users/bingzhang/clawd/myclaw-repo status --short > /tmp/openclaw-status-before.txt`.
- After exporter tests: `git -C /Users/bingzhang/clawd/myclaw-repo status --short > /tmp/openclaw-status-after.txt && diff -u /tmp/openclaw-status-before.txt /tmp/openclaw-status-after.txt`.
- Add a test that exporter default behavior rejects output paths under `/Users/bingzhang/clawd/myclaw-repo/data/world_model` unless a future explicit phase 2 flag exists; phase 1 must not provide that flag.
- Add a direct test that explicitly passing an OpenClaw `world_model` output path fails in phase 1.
- Optional phase 2 dry run: copy the export into a temp OpenClaw fixture and validate shape against a consumer, without mutating live `data/world_model`.

## ADR

Decision: implement an AI Berkshire OpenClaw exporter/schema first, using a common envelope plus product-specific OpenClaw target profiles, then plan a separate OpenClaw consumer/import step after the contract is stable.

Drivers:
- OpenClaw already owns scheduling, health, daily committee, degraded reporting, and Telegram delivery.
- AI Berkshire needs a structured artifact surface before OpenClaw can safely consume it.
- The OpenClaw worktree is currently dirty, so direct changes there would increase conflict risk.

Alternatives considered:
- Direct OpenClaw integration now: rejected for dirty-worktree and runtime-coupling risk.
- Markdown-only parsing in OpenClaw: rejected because it is brittle and weakens degradation semantics.
- Full new shared service: rejected because it duplicates OpenClaw control-plane responsibilities.

Why chosen: the exporter contract gives OpenClaw a clean input surface while keeping each repo's responsibilities intact; product-specific profiles reduce the risk that phase 1 creates a structured but unusable generic JSON.

Consequences:
- Phase 1 is not full automation; a phase 2 import step is still needed.
- AI Berkshire report discipline becomes stricter because sidecar fields and validation status must be explicit.
- The exporter is more complex than a generic schema because it must encode OpenClaw target-profile compatibility.
- OpenClaw can later choose pull, copy, or import behavior without changing the research-writing workflow.

Follow-ups:
- Implement exporter/schema/tests in AI Berkshire.
- Run a Xiaomi sample export.
- Add profile fixtures for AI bottleneck, commodity real-assets, and earnings research.
- Plan OpenClaw phase 2 importer/health entry on a clean branch.

## Available Agent Types Roster

- `explore`: fast codebase mapping and field-contract lookup.
- `executor`: implementation of exporter, schema, tests, and skill-doc edits.
- `test-engineer`: schema and sample export test design.
- `architect`: OpenClaw boundary review.
- `critic`: final plan and implementation risk review.
- `verifier`: completion evidence and no-OpenClaw-mutation checks.
- `writer`: user-facing adapter documentation polish.

## Follow-up Staffing Guidance

Default durable lane: `$ultragoal` with this plan path.
- Executor lane: implement `tools/openclaw_export.py`, schema, and tests.
- Writer lane: update `docs/openclaw-adapter.md` and relevant skill instructions.
- Test-engineer/verifier lane: validate Xiaomi export, target-profile validators, status mapping, and no OpenClaw mutation.

Parallel lane: `$team` is useful because implementation, docs, and tests can be split cleanly.
- Team worker 1: exporter/schema only.
- Team worker 2: docs and skill instruction updates.
- Team worker 3: profile validator tests and sample fixtures.
- Team verification: run targeted tests, inspect generated export, run `git status`, and confirm no files in OpenClaw changed.

Ralph fallback: use `$ralph` only if the user wants one persistent single-owner loop for implementation and verification instead of Team + Ultragoal.

## Launch Hints

```text
$ultragoal .omx/plans/openclaw-adaptation-plan-20260624T042028Z.md
$team implement .omx/plans/openclaw-adaptation-plan-20260624T042028Z.md
$ralph implement .omx/plans/openclaw-adaptation-plan-20260624T042028Z.md
```

## Goal-Mode Follow-up Suggestions

- `$ultragoal`: recommended default for durable implementation tracking.
- `$team`: recommended with Ultragoal if you want parallel implementation/doc/test lanes.
- `$autoresearch-goal`: not recommended as final lane; this is an engineering integration plan, not an open-ended research project.
- `$performance-goal`: not applicable.
- `$ralph`: acceptable explicit fallback for single-owner persistence.

## Consensus Review Changelog

- Applied Architect iteration: replaced a generic export-only contract with common envelope plus `openclaw_target_profiles`.
- Applied Architect iteration: added product-specific OpenClaw compatibility validation and made phase 2 importer OpenClaw-owned.
- Applied Critic iteration: fixed execution ambiguity with concrete profile thresholds, `tests/test_openclaw_export.py`, `tests/fixtures/openclaw/`, no-OpenClaw-mutation checks, and stdlib Python validator as schema source of truth.
- Applied Critic approval notes: updated status to consensus approved, set default output to `data/openclaw_exports/`, hardened Longbridge earnings downgrade semantics, and required explicit OpenClaw `world_model` output rejection tests.
