---
name: investment-research
description: Produce a rigorous Chinese value-investing research report for a public company using four-master analysis, two-source financial validation, and Python tool checks.
---

# Investment Research

Use this skill to create a full Chinese investment research report for the company or ticker supplied by the user.

The original Claude command source is `skills/investment-research.md`. Treat that file as methodological source material, but execute through Codex-native behavior and the repository rules in `AGENTS.md`.

## Required Output

Write the report in Chinese under:

```text
reports/{公司名}/{公司名}-research-{YYYYMMDD}.md
```

If the user asks for analysis only, provide the report content in the conversation and state the recommended output path.

## Research Sequence

1. Start with AI research bias awareness.
   - Rate information richness as A, B, or C.
   - Explain how the rating affects confidence and research strategy.
   - Distinguish AI research confidence from real investment certainty.
2. Collect current facts with citations.
   - Business segments, revenue, margins, cash flow, cash and debt, share count, market cap, valuation, management ownership, competitors, industry growth, risks, and bull/bear cases.
   - Use current web research for time-sensitive market or company facts.
3. Validate financial data.
   - Use at least two independent sources for key data where possible.
   - Run repository tools from the repo root:

```bash
python3 tools/financial_rigor.py verify-market-cap --price <price> --shares <shares> --reported <market_cap> --currency <currency>
python3 tools/financial_rigor.py cross-validate --field <field> --values '{"source1": 1, "source2": 1}' --unit <unit>
python3 tools/financial_rigor.py verify-valuation --price <price> --eps <eps> --bvps <bvps>
```

4. Analyze through four lenses.
   - Duan Yongping: business essence, customer value, differentiation, pricing power, repeat purchase, and whether the business can be explained in one sentence.
   - Buffett: financial quality, moat durability, cash generation, capital allocation, valuation, and margin of safety.
   - Munger: inversion, failure scenarios, competitive threats, incentive problems, and avoided blind spots.
   - Li Lu: long-term certainty, management quality, culture, governance, downside protection, and whether the company is knowable over ten years.
5. Build valuation.
   - Include conservative, base, and optimistic scenarios.
   - State assumptions clearly.
   - Avoid false precision.
6. Produce a decision memo.
   - Use `通过 / 有条件通过 / 灰色地带 / 不通过`.
   - Include price ranges or required conditions when appropriate.
   - Include strongest opposing evidence.

## Required Report Sections

- 一句话结论
- AI研究偏见自觉与信息丰富度评级
- 关键数据与交叉验证记录
- 生意本质分析
- 财务质量与估值
- 护城河与竞争格局
- 逆向思考与失败场景
- 管理层与治理
- 长期确定性
- 估值情景与安全边际
- 综合决策备忘录
- 数据来源与未解决问题

## Rules

- Follow `AGENTS.md` research principles.
- Use Chinese.
- Mark facts, opinions, and estimates distinctly.
- Every core claim needs evidence or an explicit uncertainty marker.
- If key data cannot be validated, stop short of a strong investment conclusion.
