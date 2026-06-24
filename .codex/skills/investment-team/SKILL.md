---
name: investment-team
description: Run a Codex-native four-lane Chinese investment research team with business, financial, industry, and risk perspectives, then synthesize a final report.
---

# Investment Team

Use this skill for a multi-perspective company research report when the user wants depth, debate, and a final Team Lead synthesis.

The original Claude command source is `skills/investment-team.md`. Treat it as methodological source material, but do not use Claude-specific team or message primitives. Execute through Codex subagents only when the user explicitly asks for parallel research or when the current Codex surface has authorized subagent use. Otherwise run the same lanes sequentially.

## Output Directory

Write outputs under:

```text
reports/{公司名}/
├── README.md
├── 01-商业模式分析-段永平视角.md
├── 02-财务估值分析-巴菲特视角.md
├── 03-行业竞争分析-芒格视角.md
├── 04-风险管理层评估-李录视角.md
└── 最终报告.md
```

## Team Lead Contract

The main Codex agent is Team Lead. It owns:

- scope, company identity, ticker, exchange, and date;
- information richness rating;
- lane assignment;
- source quality control;
- final synthesis;
- disagreement analysis;
- tool verification;
- report writing.

## Lanes

Run these four lanes in parallel when subagents are available and authorized; otherwise run them sequentially and note that in the final report metadata.

### business-analyst

Lens: Duan Yongping.

Deliver:
- business essence in one sentence;
- revenue structure and customer value;
- repeat purchase or retention drivers;
- moat sources and whether they are real;
- product or platform flywheel;
- key opposing evidence.

### financial-analyst

Lens: Buffett.

Deliver:
- 3-5 year revenue, profit, margin, cash flow, cash, debt, and share count;
- valuation multiples and historical comparison;
- capital allocation and shareholder return;
- margin of safety;
- mandatory Python validation from repository root:

```bash
python3 tools/financial_rigor.py verify-market-cap --price <price> --shares <shares> --reported <market_cap> --currency <currency>
python3 tools/financial_rigor.py cross-validate --field <field> --values '{"source1": 1, "source2": 1}' --unit <unit>
python3 tools/financial_rigor.py verify-valuation --price <price> --eps <eps> --bvps <bvps>
```

### industry-researcher

Lens: Munger.

Deliver:
- industry size, growth, structure, and profit pools;
- competitor comparison;
- inversion: how the thesis fails;
- regulatory, technology, or behavior changes that could break the business;
- non-consensus insight and strongest bear case.

### risk-assessor

Lens: Li Lu.

Deliver:
- management quality, incentives, ownership, and governance;
- culture and historical capital allocation decisions;
- long-term certainty and what could make the company unknowable;
- downside scenarios;
- final risk rating.

## Lane Output Requirements

Each lane must return:

- Markdown section or file content;
- cited sources for current facts;
- confidence markers;
- unresolved data gaps;
- `通过 / 有条件通过 / 灰色地带 / 不通过` for that lane.

## Final Synthesis

The Team Lead final report must include:

- 一句话结论
- 四维评分总表
- 四个视角的关键冲突
- 最强反方论据
- 数据验证记录
- 估值与安全边际
- 买入/观望/不买条件
- 需要继续跟踪的变量

Do not average away disagreement. If Buffett says cheap but Li Lu says unknowable, surface the tension directly.
