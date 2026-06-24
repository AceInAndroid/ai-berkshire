---
name: news-pulse
description: Quickly explain a stock price move or company news event in Chinese using current sources, four-lane checks, and clear fact/opinion separation.
---

# News Pulse

Use this skill when the user asks why a stock moved, what happened today, or how to interpret a fresh company or industry event.

The original Claude command source is `skills/news-pulse.md`. Treat it as methodological source material, but execute with Codex-native research and synthesis.

## Goal

Within a short research cycle, answer:

- What happened?
- Is it confirmed fact, market rumor, or interpretation?
- Why did the market react?
- Does it change the investment thesis?
- What should be monitored next?

## Workflow

1. Identify company, ticker, market, event date, and price move.
2. Use current web research for time-sensitive facts and cite sources.
3. Separate facts from interpretation.
4. Check four angles:
   - business impact;
   - financial or valuation impact;
   - industry and competitive context;
   - risk, governance, regulation, or management signal.
5. If financial numbers matter, use `financial-data` discipline and repository validation tools.
6. Produce a concise Chinese report.

If the user asks for OpenClaw compatibility, export the written report with:

```bash
python3 tools/openclaw_export.py --report <report.md> --skill news-pulse --symbol <ticker> --market <market> --company-name <name> --research-type news_pulse
```

Keep output under `data/openclaw_exports/`; do not write OpenClaw `world_model` files from AI Berkshire.

## Output Sections

- 结论先行
- 事件事实
- 市场反应
- 可能原因排序
- 对投资论文的影响
- 反面解释
- 需要跟踪的变量
- 数据来源

## Rules

- Do not overclaim from one news item.
- Label rumors and unconfirmed claims.
- If no reliable current source confirms the event, say so directly.
- Keep the output shorter than a full research report unless the user asks to expand.
