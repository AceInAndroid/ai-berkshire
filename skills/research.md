---
name: research
description: 自动识别上市公司、证券、行业或投资问题，并路由到 AI Berkshire 的公司研究、财报精读、估值、买入前检查、异动归因、A 股融合、行业筛选、管理层研究、组合复盘或论文跟踪工作流。用户只给公司名、问“值不值得买”“护城河是什么”“最新财报如何”“为什么大涨大跌”，或不知道该使用哪个股票 Skill 时使用。默认只读研究，不执行交易。
---

# 一键投研入口

对 $ARGUMENTS 自动选择最合适的 AI Berkshire 工作流。用户不需要记住数据源、工具命令、报告路径或验证步骤。

## 最短用法

用户只需要输入公司、证券、行业或主题：

```text
/research 腾讯
/research 苹果
/research 贵州茅台
```

在 Codex 中也可以说：

```text
使用 research 研究腾讯
```

如果没有给出模式，默认执行“标准公司研究”。

## 自动识别代码

1. 用户给了标准证券代码时直接使用，例如 `AAPL.US`、`700.HK`、`600519.SH`。
2. 用户只给公司名时，自动确认其主要上市代码，不要求用户补全。
3. 同一公司有多地上市时，默认选择主要经营所在地或流动性更高的主要上市证券，并在报告开头记录选择；ADR 作为交叉参考。
4. 如果名称确实对应多个无关实体，选择与投资研究语境最匹配的上市公司并明确标注假设，不因非关键歧义中断流程。

## 自动路由

根据用户输入中的自然语言自动选择工作流：

| 用户输入特征 | 自动执行 |
|---|---|
| 只有公司名或代码 | `investment-research` 标准公司研究 |
| 包含“快速”“简版”“10分钟” | 快速研究摘要 |
| 包含“深度”“完整” | `investment-research` 完整研究 |
| 包含“团队”“四大师” | `investment-team` |
| 包含“财报”“年报”“季报”“业绩” | `earnings-review` |
| 包含“财报团队” | `earnings-team` |
| 包含“估值”“内在价值”“安全边际”“目标价” | `company-valuation`（可用时），否则使用 `investment-research` 估值模块 |
| 包含“是否买入”“买点”“买入时机”“当前能买吗” | `investment-checklist` + 估值；A 股需要市场/资金验证时追加 `tradingagents-astock`，趋势确认可追加 `sepa-strategy` |
| 包含“护城河”“商业模式”“竞争优势” | `investment-research`；核心争议是人时追加 `management-deep-dive` |
| 包含“异动”“大涨”“大跌”“发生了什么” | `news-pulse` |
| 包含多个公司并出现“对比”“比较” | `investment-checklist` |
| 包含“管理层”“CEO”“创始人” | `management-deep-dive` |
| 包含“行业”“产业链” | `industry-research` |
| 包含“筛选”“选股”“找公司” | `industry-funnel`，必要时接 `quality-screen` |
| 包含“持仓”“组合” | `portfolio-review` |
| 包含“论文追踪”“买入后” | `thesis-tracker` |
| 包含“系列”“8篇” | `deep-company-series` |
| A 股且包含“多空辩论”“量化验证”“回测”“三套框架融合” | `tradingagents-astock` |

常用 Codex App 入口：

| App Skill | 用途 | 典型输入 |
|---|---|---|
| `$research` | 不确定用哪个工作流时的总入口 | `研究特斯拉当前是否值得买` |
| `$investment-research` | 单家公司长期价值和护城河 | `研究腾讯的商业模式与护城河` |
| `$earnings-review` | 最新或指定期间财报 | `精读特斯拉 2026Q2 财报` |
| `$investment-checklist` | 买入前质量、估值与风险检查 | `检查贵州茅台当前是否通过买入清单` |
| `$tradingagents-astock` | A 股长期价值与短期市场融合 | `研究 600519.SH 当前的资金与多空分歧` |
| `$news-pulse` | 股价异动和事件归因 | `调查宁德时代今天为什么大跌` |
| `$industry-funnel` | 从行业筛选候选公司 | `从 AI 算力产业链筛选 3 家公司` |
| `$portfolio-review` | 组合结构和风险复盘 | `复盘我的持仓结构` |
| `$thesis-tracker` | 买入后的论文跟踪 | `更新拼多多投资论文` |

在 Codex App 中优先使用 `$skill-name` 或从 Skills 页面选择卡片。`/prompts:*` 是 CLI/IDE 的旧兼容入口，不作为 App 主路由。

如果同时命中多个意图，优先级为：

```text
用户明确指定的模式
→ 财报/异动等时效任务
→ 买入时点与估值任务
→ 多公司对比或行业筛选
→ 标准公司研究
```

## 零配置默认值

用户没有额外说明时，自动采用以下设置：

- 语言：中文
- 研究立场：不预设看多或看空
- 数据日期：执行当天
- 数据源：Longbridge MCP + 原始披露或第二独立来源；A 股融合模式可补充 TradingAgents-astock 与 Vibe-Trading
- Longbridge 权限：只读市场和公司数据
- 计算：`tools/financial_rigor.py`
- 报告抽检：`tools/report_audit.py`
- 报告目录：`reports/{公司名}/`
- 报告文件：`{公司名}-research-{YYYYMMDD}.md`
- 估值：乐观、中性、悲观三情景
- 输出：核心结论、反面论据、风险、估值区间和待验证问题

## Longbridge 自动取数

Longbridge MCP 可用时，自动按 `skills/longbridge-data.md` 获取最小必要的数据：

- 服务时间和行情时间戳
- 证券静态信息
- 当前行情和市值指标
- 公司资料和业务分部
- 最新财务摘要和三张表
- 当前估值和历史估值
- 分红、公司行动、股东和机构评级
- 与研究问题相关的新闻、公告和事件

Longbridge 所有工具合计只算一个第三方来源，不能通过多个 Longbridge 工具伪造双源验证。

## A 股融合研究

研究对象为 A 股，且用户要求多空辩论、技术/资金面、因子、回测或融合研究时，自动执行 `skills/tradingagents-astock.md`：

- AI Berkshire 负责商业质量、管理层、财务核验、估值和最终结论。
- TradingAgents-astock MCP 默认通过 `prepare_codex_native_research` 准备角色计划，由当前 Codex 模型及其原生子代理完成 A 股多角色分析、Bull/Bear 辩论和风险观点，不需要外部 LLM Provider。只有用户明确要求原版上游图且其状态 ready 时，才使用异步 `start/status/result`。
- Vibe-Trading MCP 负责只读行情和资金流；因子分析限本次任务隔离目录，回测因会执行本地策略代码，必须先审查并取得用户对本次执行的明确授权。
- Longbridge 可作为结构化取数层，但原始披露或另一独立来源仍不可省略。

三个 MCP 各自内部的多个工具只算各自一个聚合来源；若底层数据相同，也不能互相构成双源。TradingAgents 的 Agent 观点不是独立财务数据来源。

## 自动验证

标准公司研究至少验证：

1. 当前股价和行情日期
2. 总股本和市值
3. 最近财年收入和净利润
4. 经营现金流和自由现金流
5. 现金、短期投资和有息负债
6. EPS、BPS、PE、PB、ROE 和 FCF Yield

自动执行：

```bash
python3 tools/financial_rigor.py verify-market-cap ...
python3 tools/financial_rigor.py cross-validate ...
python3 tools/financial_rigor.py verify-valuation ...
python3 tools/financial_rigor.py three-scenario ...
```

报告完成后自动运行：

```bash
python3 tools/report_audit.py extract --report <报告路径>
python3 tools/report_audit.py verdict --results '<核验结果>' --report <报告路径>
```

如果第二来源或原始披露暂时无法获得，不得伪造验证结果；在报告中标记“单源待核验”和具体缺口。

## 快速模式

当用户输入“快速”“简版”或“10分钟”时：

1. 使用 Longbridge 获取行情、公司、最新财务、估值和近期新闻。
2. 使用一个独立来源验证收入、净利润、股价和市值。
3. 输出不超过约 1500 字的摘要，包括：
   - 一句话结论
   - 生意模式
   - 三个关键数字
   - 当前估值
   - 三个主要风险
   - 是否值得进入完整研究
4. 保存为 `reports/{公司名}/{公司名}-quick-{YYYYMMDD}.md`。
5. 快速模式不等于降低数据真实性要求；无法验证的数据必须标记。

## 安全边界

本入口永久禁止调用 Longbridge 的：

- 下单、撤单、改单工具
- 定投创建、修改、暂停、恢复和终止工具
- 提醒、自选股和社区写入工具

本入口永久禁止调用 Vibe-Trading 的 `write_file`、`run_swarm`、Shell、连接器选择、券商、账户和交易工具；不得启用 `--enable-shell-tools`。TradingAgents-astock 只允许研究任务与状态/结果查询，不接受凭证、任意 endpoint、文件路径或命令，也不执行交易。

默认不读取个人账户余额、持仓、订单、银行卡、入金或出金。

只有用户明确说“读取我的 Longbridge 持仓进行组合分析”时，才允许在 `portfolio-review` 中读取必要的账户只读数据；仍然禁止任何交易和写入操作。

## 完成标准

任务完成时必须满足：

- 已自动识别研究对象和证券代码
- 已选择正确的 AI Berkshire 工作流
- Longbridge 数据带有时间戳和报告期
- 关键数据有第二来源或明确标记未验证
- 计算由 `financial_rigor.py` 完成
- 报告通过 `report_audit.py`，或明确说明未通过原因
- 报告已写入约定目录
- 没有执行账户写入或交易操作
