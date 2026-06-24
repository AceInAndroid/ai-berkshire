# OpenClaw Adaptation Context Snapshot

Task statement: adapt AI Berkshire so its Codex skills, investment reports, and validation tools can produce OpenClaw-consumable research artifacts.

Desired outcome: AI Berkshire should remain a research/reporting repo, while emitting structured sidecar JSON and optional export bundles that OpenClaw can ingest through its existing world model, assistant-mode scheduler, health checks, daily investment committee, and briefing flows.

Known facts and evidence:
- AI Berkshire already has Codex skill derivatives under `.codex/skills/<skill-name>/SKILL.md`; `docs/codex-usage.md` documents the Codex entrypoints and validation commands.
- AI Berkshire has validation tooling: `tools/financial_rigor.py` for market cap, valuation, and cross-source checks; `tools/report_audit.py` for extracting and judging report data points.
- OpenClaw authority is `/Users/bingzhang/clawd/myclaw-repo`; `/Users/bingzhang/Documents/myclaw` is a symlink and should not be treated as a second authority.
- OpenClaw `scripts/jobs/daily_investment_committee.py` reads:
  - `data/world_model/ai_bottleneck_research/latest.json`
  - `data/world_model/commodity_real_assets_research/latest.json`
  - `data/world_model/earnings_season_research/latest.json`
  - `data/world_model/committee_runs/daily_ic_*.json`
- OpenClaw `daily_ic` preserves those research payloads on both normal and degraded outputs.
- OpenClaw `scripts/assistant_mode_scheduler.py` reruns the three research product scripts before the committee stage in `committee`.
- OpenClaw `scripts/daily_operating_briefing.py` consumes latest `daily_ic` and explicitly renders degraded state.
- OpenClaw health checks already inspect AI bottleneck research freshness and coverage in `scripts/data_source_health_check.py`.

Constraints:
- Do not invent a parallel OpenClaw scheduler or committee chain.
- Do not write into OpenClaw's dirty worktree during planning.
- First implementation should be low-risk and mostly contained in AI Berkshire.
- OpenClaw degraded semantics must be preserved; AI Berkshire must not mask stale or weak evidence as healthy.
- Longbridge remains OpenClaw's primary earnings source priority where OpenClaw already owns filing/financial-report/consensus/calendar ingestion.

Unknowns/open questions:
- Exact final sidecar schema should be confirmed against a sample OpenClaw consumer once implementation begins.
- Whether OpenClaw should consume AI Berkshire artifacts by copy, symlink, or explicit import should be decided after the exporter exists.
- Commodity/real-assets mapping is likely not covered by current AI Berkshire skills and may need a later separate adapter.

Likely AI Berkshire touchpoints:
- `AGENTS.md`
- `docs/codex-usage.md`
- `.codex/skills/investment-research/SKILL.md`
- `.codex/skills/news-pulse/SKILL.md`
- `.codex/skills/earnings-review/SKILL.md`
- `.codex/skills/bottleneck-hunter/SKILL.md`
- `tools/report_audit.py`
- `tools/financial_rigor.py`
- new adapter module/script under `tools/` or `openclaw/`
- new schema/examples/tests under `tests/` or `docs/`

Likely OpenClaw touchpoints for later implementation:
- `/Users/bingzhang/clawd/myclaw-repo/scripts/jobs/daily_investment_committee.py`
- `/Users/bingzhang/clawd/myclaw-repo/scripts/assistant_mode_scheduler.py`
- `/Users/bingzhang/clawd/myclaw-repo/scripts/data_source_health_check.py`
- `/Users/bingzhang/clawd/myclaw-repo/data/world_model/*_research/latest.json`
