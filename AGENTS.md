# AI Berkshire Codex Instructions

## Project

AI Berkshire is a value-investing research workflow repository. It systematizes the methods of Warren Buffett, Charlie Munger, Duan Yongping, and Li Lu into reusable research skills, report templates, and Python validation tools.

## Structure

- `skills/` contains the original Claude Code command sources.
- `.codex/skills/` contains Codex-adapted skills for this local OMX/Codex profile.
- `tools/` contains validation helpers such as `financial_rigor.py` and `report_audit.py`.
- `reports/` contains generated investment research reports.
- `assets/` contains static assets.
- `.omx/plans/` contains migration and workflow planning artifacts.

## Skill Source Of Truth

During the dual-mode migration, treat `skills/*.md` as the Claude command source and `.codex/skills/*/SKILL.md` as Codex-adapted derivatives. When changing a Claude skill, update the paired Codex skill or explicitly mark the Codex skill stale in the change notes.

This checkout targets `.codex/skills` because the installed OMX/Codex profile loads project-local skills from that path. Public stock Codex distributions may need `.agents/skills` or plugin packaging; verify discovery before publishing.

## Report Layout

Company-specific reports go under `reports/{公司名}/`. Industry, funnel, theme, portfolio, and multi-company reports may live under `reports/` root.

Use these naming conventions:

| Workflow | File pattern |
| --- | --- |
| `investment-team` | `reports/{公司名}/README.md`, four perspective files, and `reports/{公司名}/最终报告.md` |
| `investment-research` | `reports/{公司名}/{公司名}-research-{YYYYMMDD}.md` |
| `investment-checklist` | `reports/{公司名}/{公司名}-checklist-{YYYYMMDD}.md` |
| `industry-research` | `reports/{行业名}-industry-{YYYYMMDD}.md` |
| `industry-funnel` | `reports/{行业名}-funnel-{YYYYMMDD}.md` |
| `private-company-research` | `reports/{公司名}/{公司名}-private-{YYYYMMDD}.md` |
| `earnings-review` | `reports/{公司名}/{公司名}-earnings-{期间}.md` |
| `thesis-tracker` | `reports/{公司名}/{公司名}-thesis.md` |
| `portfolio-review` | `reports/portfolio-latest.md` |
| `management-deep-dive` | `reports/{公司名}/{公司名}-management-{YYYYMMDD}.md` |

For `investment-team`, use:

```text
reports/{公司名}/
├── README.md
├── 01-商业模式分析-段永平视角.md
├── 02-财务估值分析-巴菲特视角.md
├── 03-行业竞争分析-芒格视角.md
├── 04-风险管理层评估-李录视角.md
└── 最终报告.md
```

## Research Principles

- Be objective. Base every investment analysis on facts and data, not a preselected bullish or bearish stance.
- Strictly separate facts from opinions. Facts need data and citations; opinions must be labeled as `观点` or `推测`.
- Start with data, then logic, then conclusion. The conclusion must follow from the evidence.
- Avoid subjective language such as `我认为`, `我觉得`, and `显然`. Prefer `数据显示`, `证据表明`, and `根据XX来源`.
- Present the strongest opposing evidence for every core claim.
- Say `不确定` or `数据不足` when evidence is insufficient. Do not fill gaps with false certainty.
- All reports must be written in Chinese.
- Use a direct, sharp, no-filler style.
- Mark estimates as `估计`.
- Use ★ ratings from 1 to 5, with no half stars.
- Key financial data must cite sources and use at least two independent sources when possible.

## Financial Verification

Never rely on mental math for market cap, PE, ROE, FCF yield, or scenario valuation.

From the repository root, use:

```bash
python3 tools/financial_rigor.py verify-market-cap --price <price> --shares <shares> --reported <market_cap> --currency <currency>
python3 tools/financial_rigor.py cross-validate --field <field> --values '{"source1": 1, "source2": 1}' --unit <unit>
python3 tools/financial_rigor.py verify-valuation --price <price> --eps <eps> --bvps <bvps>
python3 tools/report_audit.py extract --report <report.md>
python3 tools/report_audit.py verdict --results '<json-results>'
```

If a validation tool reports a material discrepancy, investigate and document the discrepancy before continuing analysis.

## OpenClaw Export Boundary

When adapting a report for OpenClaw, generate AI Berkshire export artifacts with `tools/openclaw_export.py`. The default output is `data/openclaw_exports/`.

Do not write into `/Users/bingzhang/clawd/myclaw-repo/data/world_model` from this repository. OpenClaw owns import, health checks, daily investment committee inclusion, degraded state, briefing, and delivery.

## Git And Output Hygiene

- Remote repository: `https://github.com/xbtlin/ai-berkshire.git`.
- Before pushing, run `git pull --rebase origin main`.
- Do not commit intermediate scratch files such as `data_collection.md`; commit final reports and durable workflow artifacts only.
- Do not push without an explicit user request.
