# Codex Usage

This repository was originally written for Claude Code commands under `skills/*.md`. The current Codex adaptation keeps those Claude sources and adds Codex-native skill derivatives under `.codex/skills`.

## Skill Locations

For this local OMX/Codex setup, project skills load from:

```text
.codex/skills/<skill-name>/SKILL.md
```

The public Codex manual documents repo skills under `.agents/skills`. If you want to publish or share this project for stock Codex users, verify skill discovery in that environment or package the skills as a Codex plugin.

## Invocation

Use Codex skill invocation with `$`:

```text
$investment-research 腾讯
$investment-team 美团
$financial-data PDD revenue and market cap
$news-pulse 腾讯
```

Claude users can continue using the original slash commands after copying `skills/*.md` to their Claude commands directory.

## Source Of Truth

During migration:

- `skills/*.md` remains the Claude command source.
- `.codex/skills/*/SKILL.md` is the Codex-adapted derivative.
- When a Claude skill changes, update the paired Codex skill or explicitly mark it stale.

Run this drift check after changes:

```bash
rg -n "TeamCreate|TaskCreate|TaskUpdate|SendMessage|WebSearch|\\$ARGUMENTS|~/ai-berkshire|~/.claude" .codex/skills AGENTS.md README.md
```

Remaining matches should be either absent from Codex skill instructions or explicitly documented as Claude-only compatibility notes.

## Validation Tools

Run validation from the repository root:

```bash
python3 tools/financial_rigor.py verify-market-cap --price <price> --shares <shares> --reported <market_cap> --currency <currency>
python3 tools/financial_rigor.py cross-validate --field <field> --values '{"source1": 1, "source2": 1}' --unit <unit>
python3 tools/financial_rigor.py verify-valuation --price <price> --eps <eps> --bvps <bvps>
python3 tools/report_audit.py extract --report <report.md>
python3 tools/report_audit.py verdict --results '<json-results>'
```

Do not use LLM mental math for financial calculations that affect an investment conclusion.

## OpenClaw Exports

When a report needs to be consumable by OpenClaw, use the phase 1 exporter:

```bash
python3 tools/openclaw_export.py --report <report.md> --skill <skill-name> --symbol <ticker> --market <market> --company-name <name> --research-type <type>
```

Default output is `data/openclaw_exports/`. The exporter refuses to write under `/Users/bingzhang/clawd/myclaw-repo/data/world_model` during phase 1. See `docs/openclaw-adapter.md`.
