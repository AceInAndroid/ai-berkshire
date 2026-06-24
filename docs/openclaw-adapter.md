# OpenClaw Adapter

AI Berkshire can export Codex-generated research reports into OpenClaw-compatible JSON artifacts. This is a phase 1 adapter: it creates AI Berkshire artifacts only and does not mutate OpenClaw runtime state.

## Boundary

- OpenClaw authority: `/Users/bingzhang/clawd/myclaw-repo`
- `/Users/bingzhang/Documents/myclaw` is a symlink to the same OpenClaw repo. Do not treat it as a separate authority.
- AI Berkshire writes exports under `data/openclaw_exports/` by default.
- Phase 1 must not write into `/Users/bingzhang/clawd/myclaw-repo/data/world_model`.
- OpenClaw remains responsible for import, health checks, daily investment committee inclusion, degraded state, briefing, and delivery.

## Export Command

Run from the AI Berkshire repository root:

```bash
python3 tools/openclaw_export.py \
  --report reports/小米/小米-research-20260624.md \
  --skill investment-research \
  --symbol 1810.HK \
  --market HK \
  --company-name 小米集团 \
  --research-type company_research \
  --output-dir data/openclaw_exports
```

The exporter writes:

- a timestamped JSON artifact
- a `{research_type}_latest.json` pointer artifact

## Target Profiles

The exporter supports OpenClaw target-profile validation for products that resemble OpenClaw world-model research artifacts:

- `ai_bottleneck_research`
- `commodity_real_assets_research`
- `earnings_season_research`

Profiles fail closed. A single-company report should not pass as healthy AI bottleneck or commodity research. Earnings exports must preserve Longbridge provenance; yfinance-only or narrative-only evidence is degraded.

Example:

```bash
python3 tools/openclaw_export.py \
  --report reports/小米/小米-research-20260624.md \
  --skill investment-research \
  --symbol 1810.HK \
  --market HK \
  --company-name 小米集团 \
  --research-type earnings_review \
  --target-profile earnings_season_research \
  --output-dir data/openclaw_exports
```

If the report lacks required OpenClaw evidence, the export still writes an artifact, but marks it `degraded` or `critical` with profile errors.

## Verification

Run:

```bash
git -C /Users/bingzhang/clawd/myclaw-repo status --short > /tmp/openclaw-status-before.txt
python3 -m unittest tests/test_openclaw_export.py
git -C /Users/bingzhang/clawd/myclaw-repo status --short > /tmp/openclaw-status-after.txt
diff -u /tmp/openclaw-status-before.txt /tmp/openclaw-status-after.txt
```

The diff must be empty. If it is not empty, phase 1 violated the no-OpenClaw-mutation boundary.

