---
name: research
description: "AI Berkshire skill: 一键投研入口. Source: skills/research.md."
---

## Codex adapter note

This skill is generated from `skills/research.md` so Claude Code and Codex users share one canonical workflow.

- Treat `$ARGUMENTS` as the user's request in the current Codex thread.
- When the source mentions Claude-only surfaces such as Task, Agent, WebSearch, Bash, Read, or Write, use the closest Codex capability available in this session: subagents when available, web search when needed, shell commands for local tools, and normal file edits for workspace files.
- Use shared project tools from `tools/` in this repository. Commands that reference `~/ai-berkshire/tools/...` assume the repo is checked out at `~/ai-berkshire`; if needed, prefer the current workspace path.
- Preserve the research quality rules from `AGENTS.md`: cross-check financial data, use exact arithmetic tools for valuation/math, and clearly label uncertainty and source gaps.

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
| 包含“异动”“大涨”“大跌”“发生了什么” | `news-pulse` |
| 包含多个公司并出现“对比”“比较” | `investment-checklist` |
| 包含“管理层”“CEO”“创始人” | `management-deep-dive` |
| 包含“行业”“产业链” | `industry-research` |
| 包含“筛选”“选股”“找公司” | `industry-funnel`，必要时接 `quality-screen` |
| 包含“持仓”“组合” | `portfolio-review` |
| 包含“论文追踪”“买入后” | `thesis-tracker` |
| 包含“系列”“8篇” | `deep-company-series` |

如果同时命中多个意图，优先级为：

```text
用户明确指定的模式
→ 财报/异动等时效任务
→ 多公司对比或行业筛选
→ 标准公司研究
```

## 零配置默认值

用户没有额外说明时，自动采用以下设置：

- 语言：中文
- 研究立场：不预设看多或看空
- 数据日期：执行当天
- 数据源：Longbridge MCP + 原始披露或第二独立来源
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
