---
name: financial-data
description: Validate company financial data in Chinese investment research using two independent sources, explicit discrepancy handling, and repository Python tools.
---

# Financial Data Validation

Use this skill when a report, thesis, checklist, or quick answer depends on financial data such as revenue, profit, cash, debt, shares, market cap, valuation multiples, ROE, FCF, or dividends.

## Required Workflow

1. Identify the security, exchange, ticker, reporting currency, and period.
2. Gather each key data point from at least two independent sources when available.
3. Prefer primary filings or exchange disclosures when third-party sources disagree.
4. Mark estimates as `估计`.
5. Compute discrepancies:

```text
误差率 = |来源1数值 - 来源2数值| / 来源1数值 * 100%
```

Use this handling:

| Difference | Handling |
| --- | --- |
| `<= 1%` | Treat as consistent, cite both sources. |
| `1% - 5%` | Mark as data discrepancy and explain likely causes. |
| `> 5%` | Treat as major discrepancy; verify against primary filings before using. |

## Source Priorities

For US-listed companies, use Macrotrends, StockAnalysis, and SEC filings where applicable.

For Hong Kong-listed companies, use AAStocks, HKEX filings, and ADR data where applicable.

For A-share companies, use Eastmoney and CNINFO filings.

For private companies, mark data as `估计` when only one credible source exists.

## Tool Checks

Run commands from the repository root.

```bash
python3 tools/financial_rigor.py verify-market-cap --price <price> --shares <shares> --reported <market_cap> --currency <currency>
python3 tools/financial_rigor.py cross-validate --field <field> --values '{"source1": 1, "source2": 1}' --unit <unit>
python3 tools/financial_rigor.py verify-valuation --price <price> --eps <eps> --bvps <bvps>
```

Embed the tool output or a concise summary in the report's validation appendix.

## Output Format

For each important data point, report:

```text
收入：1,239亿元
- 来源A：1,241亿元
- 来源B：1,237亿元
- 误差：0.3%
- 处理：一致，采用来源A口径
```

If data is inconsistent, state the discrepancy and do not hide uncertainty.
