# Longbridge MCP 只读投研数据底稿

使用 Longbridge MCP 为 $ARGUMENTS 生成可追溯的结构化投研数据底稿。

本 Skill 只负责**取数和记录数据口径**，不直接形成买卖建议。所有计算与多源验证继续使用仓库现有的 `tools/financial_rigor.py` 和 `tools/report_audit.py`。

## 输入

推荐格式：

```text
{证券代码} {研究目的或所需数据}
```

示例：

```text
AAPL.US 公司资料、最新财报、估值和近一年股价
700.HK 财务报表、业务分部、机构评级和股东结构
600519.SH 最新行情、估值、分红和公司行动
```

证券代码必须使用 Longbridge 的 `<代码>.<市场>` 格式，例如：

- 美股：`AAPL.US`、`PDD.US`
- 港股：`700.HK`、`3690.HK`
- A 股：`600519.SH`、`000858.SZ`

如果用户只给公司名，先使用只读证券搜索或静态信息工具确认代码，不得凭记忆猜测。

## 前置检查

1. 确认当前会话暴露了 Longbridge MCP 工具；Codex 中通常显示为 `mcp__longbridge` 命名空间。
2. 如果工具不可用，明确说明“Longbridge MCP 未连接”，并按 `docs/longbridge-mcp.md` 提供的方式配置；不得伪造 Longbridge 返回值。
3. 调用 `now` 记录 Longbridge 服务端 UTC 时间，作为本次底稿的统一 `as_of`。
4. 所有调用保持只读。

## 安全边界

### 默认禁止账户数据

除非用户明确要求分析其本人组合，并且当前任务确实需要，否则不得读取：

- 账户余额、银行卡、入金、出金
- 当前持仓、基金持仓、融资融券信息
- 当日或历史订单、成交、结单
- IPO 订单和个人盈亏

### 永久禁止写入和交易工具

本仓库的投研 Skill 不得调用以下工具：

```text
submit_order
cancel_order
replace_order
dca_create
dca_pause
dca_resume
dca_stop
dca_update
alert_add
alert_delete
alert_disable
alert_enable
create_watchlist_group
delete_watchlist_group
update_watchlist_group
sharelist_add
sharelist_create
sharelist_delete
sharelist_remove
sharelist_sort
topic_create
topic_create_reply
```

即使工具在当前会话中可见，也不能把“可见”解释为“允许使用”。交易执行不属于本仓库职责。

## 标准取数流程

根据研究目的调用最小必要的只读工具，避免无关账户数据和超长响应。

### 1. 身份和行情快照

优先调用：

- `static_info`：名称、交易所、证券类型、上市日期、每手股数
- `quote`：最新价、前收、OHLC、成交量、常规/盘前/盘后/夜盘时间戳
- `calc_indexes`：市值、PE TTM、PB、股息率、换手率等明确口径的指标
- `market_status`：必要时确认市场是否开市

### 2. 公司和业务结构

按需调用：

- `company`
- `business_segments`
- `business_segments_history`
- `executive`
- `operating`（港股）
- `constituent`（指数或 ETF）

### 3. 财务数据

按需调用：

- `financial_report_latest`：快速摘要
- `financial_statement` 或 `financial_report`：利润表、资产负债表、现金流量表
- `financial_report_snapshot`：实际值、预测值和财务比率
- `forecast_eps`
- `consensus`

不得只因为 `financial_report_latest` 返回了摘要，就跳过现金流量表或原始财报。

### 4. 估值和资本市场信息

按需调用：

- `valuation`
- `valuation_history`
- `valuation_rank`
- `industry_valuation`
- `industry_valuation_dist`
- `institution_rating`
- `institution_rating_detail`
- `shareholder_top`
- `fund_holder`
- `dividend`
- `corp_action`

`valuation` 的描述性区间只能作为背景。PE、PB、ROE、FCF Yield 和市值必须用 `tools/financial_rigor.py` 根据底层数据重新验算。

### 5. 原始披露、新闻和事件

按需调用：

- `filings`
- `invest_relation`
- `news`
- `news_search`
- `finance_calendar`

`filings` 返回的索引、标题或摘要不等于已阅读原始文件。只有实际打开并核对监管文件或公司公告正文后，才能标记为“原始一手来源”。

### 6. 行情历史和市场结构

按需调用：

- `candlesticks`
- `history_candlesticks_by_date`
- `intraday`
- `depth`
- `trades`
- `capital_flow`
- `short_positions`
- `option_chain_info_by_date`
- `top_movers`

不得为了“数据看起来丰富”而拉取与研究问题无关的全量历史序列。

## 来源独立性规则

**Longbridge 整体只算一个第三方数据源。**

以下情况不构成双源验证：

- `financial_report_latest` + `financial_statement`
- `quote` + `calc_indexes`
- `valuation` + `valuation_history`
- 两个不同 Longbridge 工具返回同一个指标

关键数据仍需配对另一个独立来源：

- 美股：SEC / 公司 IR 原文，或独立财务数据库
- 港股：HKEX 披露易 / 公司公告，或独立财务数据库
- A 股：巨潮资讯 / 交易所公告，或独立财务数据库

如果 Longbridge 与原始披露冲突，以原始披露为准，并在报告中保留差异记录。

## 输出格式

输出一份“Longbridge 数据底稿”，至少包含：

```markdown
# Longbridge 数据底稿：{symbol}

- Longbridge 服务时间：{UTC时间}
- 证券代码：{symbol}
- 研究目的：{purpose}
- 调用工具：{tool list}
- 是否读取账户数据：否/是（说明原因）
- 是否执行写操作：否

## 关键数据

| 指标 | 数值 | 币种/单位 | 报告期或时间戳 | Longbridge 工具 | 口径说明 |
|---|---:|---|---|---|---|

## 缺失与口径风险

- 缺失字段
- 数据更新时间不明确的字段
- GAAP / Non-GAAP、TTM / 静态 / 预测口径问题
- 需要从原始披露确认的项目

## 双源验证待办

| 指标 | Longbridge 值 | 第二来源 | 状态 |
|---|---:|---|---|
```

## 接入现有验证工具

将 Longbridge 和独立来源的值传入：

```bash
python3 tools/financial_rigor.py cross-validate \
  --field revenue \
  --values '{"Longbridge": 1000000000, "公司年报": 995000000}' \
  --unit USD
```

对市值和估值继续执行：

```bash
python3 tools/financial_rigor.py verify-market-cap \
  --price {price} --shares {shares} --reported {market_cap} --currency {currency}

python3 tools/financial_rigor.py verify-valuation \
  --price {price} --eps {eps} --bvps {bvps} --fcf-per-share {fcf_per_share}
```

报告完成后，使用 `tools/report_audit.py` 做抽检准出。
