# TradingAgents-astock × AI Berkshire 集成与使用教程

> 验证范围：2026-07-24；适配目标为 [TradingAgents-astock v0.2.21](https://github.com/simonlin1212/TradingAgents-astock/tree/v0.2.21)。

AI Berkshire 通过本仓库的 MCP 适配器融合 TradingAgents-astock。默认 `codex_native` 模式由当前 Codex 对话模型及其原生子代理执行 TradingAgents 角色拓扑，不需要另配 LLM Provider、模型名或 API Key。原版上游图仍可作为可选模式运行。适配器不提供下单、券商账户、任意命令、文件或 endpoint 参数。

## 目录

- [先看结论](#先看结论)
- [研究方法论](#研究方法论)
- [使用方法](#使用方法)
- [五分钟快速开始](#五分钟快速开始)
- [架构与边界](#架构与边界)
- [如何组合其他股票 Skill](#如何组合其他股票-skill)
- [完整使用示例](#完整使用示例)
- [安装](#安装)
- [两种执行模式](#两种执行模式)
- [注册 stdio MCP](#注册-stdio-mcp)
- [MCP 工具](#mcp-工具)
- [验收](#验收)
- [常见问题与排错](#常见问题与排错)
- [更新与卸载](#更新与卸载)
- [许可证与风险](#许可证与风险)

## 先看结论

日常使用时不需要手动调用 MCP 工具，也不需要记住所有 Skill。把公司和研究目标告诉 Codex 即可：

```text
使用 tradingagents-astock 对贵州茅台做标准深度融合研究。
默认 Codex-native，只读；AI Berkshire 负责财务核验、估值和最终结论，
TradingAgents 做多角色辩论，Vibe-Trading 验证行情和资金面。
```

系统应当依次完成：标的识别 → 原始披露与第二来源核验 → TradingAgents 证据角色 → Bull/Bear/Risk 辩论 → Vibe 行情和资金验证 → 精确估值 → 冲突裁决 → 报告审计。

三个概念不要混淆：

| 概念 | 本质 | 在本项目中的位置 |
|---|---|---|
| Skill | 可重复执行的研究方法和约束 | 规定“怎么研究” |
| MCP | 数据或程序能力的受控接口 | 负责取数、校验请求或运行上游图 |
| 原生子代理 | 当前 Codex 模型下的并行研究角色 | 负责独立证据收集和多空审视 |

AI Berkshire 始终是最终编排层。TradingAgents 的结论是观点，Vibe/Longbridge 是聚合数据，原始公告和可审计计算才是事实层。

## 研究方法论

这套融合研究不是把多个 Agent 的结论投票平均，而是把不同类型的证据放到正确的位置。最终要把四个问题分开回答：

1. **是不是好公司**：商业模式、护城河、管理层和财务质量是否可靠。
2. **是不是好价格**：当前价格相对可审计的内在价值是否有安全边际。
3. **是不是好时点**：短期量价、资金、事件和政策环境是否增加入场风险。
4. **什么会证明我们错了**：哪些事实出现后应降低置信度或判定论文失效。

### 双时钟：避免长期价值与短期交易信号互相覆盖

| 维度 | 长期价值时钟 | 短期市场时钟 |
|---|---|---|
| 常用窗口 | 3—5 年 | 数日到数月 |
| 核心问题 | 内在价值能否持续增长 | 市场当前在交易什么 |
| 主要研究对象 | 商业模式、护城河、治理、财务、资本配置、估值 | 量价、成交、资金流、政策、新闻、情绪、解禁、催化剂 |
| 结果形式 | 是否值得拥有、价值区间、长期失效条件 | 信号方向、有效窗口、短期失效条件 |
| 常见误用 | 因为公司优秀就忽略价格 | 因为股价走弱就否定公司价值 |

报告必须先分别给出两个时钟的结论，再写融合判断。例如：

```text
长期价值：商业质量未变，基准价值区间高于现价，但安全边际一般。
短期信号：资金连续转弱，政策催化尚未兑现，未来 20 个交易日风险偏高。
融合判断：公司质量门通过，估值门临界，时点门未通过；列入观察而非否定长期论文。
```

### 四层证据：避免把观点伪装成事实

```text
事实层 → 解释层 → 信号层 → 决策层
```

| 层级 | 需要回答 | 示例 | 审核要求 |
|---|---|---|---|
| 事实层 | 发生了什么 | 收入、自由现金流、股份数、收盘价、公告日期 | 来源、抓取时间、报告期、币种、单位、独立性 |
| 解释层 | 为什么重要 | 毛利下降源于价格战还是产品结构 | 写出因果链、替代解释和反证 |
| 信号层 | 市场如何反应 | 放量下跌、北向变化、解禁窗口、情绪拐点 | 记录频率、窗口、复权口径、样本和有效期 |
| 决策层 | 现在如何处理 | 深入研究、观察、等待验证、风险上升、论文失效 | 同时通过质量、估值和时点审查 |

每条关键结论使用同一证据卡：

```text
claim: 可检验的结论
evidence: 数据、原文或可复现计算
source: 发布者、URL、报告期、抓取时间
counterevidence: 相反证据或替代解释
confidence: high / medium / low
gaps: 尚缺什么才能提高置信度
```

Agent 观点不能填入事实层。Longbridge、Vibe-Trading 或 TradingAgents 即使返回多个工具结果，只要底层数据来自同一聚合商或同一公告，也不能被算作多个独立来源。

### 三道决策门：好公司、好价格、好时点

研究按顺序通过三道门：

| 决策门 | 通过条件 | 不通过时的结论 |
|---|---|---|
| 公司质量门 | 商业模式可理解；护城河有事实支持；治理可信；现金流和资本配置支持叙事 | 停止讨论“便宜”，归为质量风险或论文失效 |
| 估值安全边际门 | 悲观、基准、乐观情景输入可审计；现价相对价值区间有足够安全边际 | 等待价格、等待数据或降低预期回报 |
| 时点与风险门 | 市场结构、资金、流动性、政策和事件风险可接受 | 长期结论保留，但给出等待条件和信号失效点 |

“当前是否适合买入”不是一个单指标问题。应使用下面的组合判断：

| 公司质量 | 安全边际 | 短期环境 | 研究结论 |
|---|---|---|---|
| 不通过 | 任意 | 任意 | 不因低估值买入，先解决质量疑问 |
| 通过 | 不足 | 任意 | 好公司但价格不合适，等待估值改善 |
| 通过 | 充足 | 不利 | 长期有吸引力、短期风险偏高；定义观察或分阶段验证条件 |
| 通过 | 充足 | 中性或有利 | 进入投资决策候选，但仍需结合个人组合、期限和风险承受能力 |

本项目输出研究判断，不代替个人适当性评估，也不会自动下单。

### 八步研究闭环

| 步骤 | 操作 | 必须产物 | 停止或降级条件 |
|---|---|---|---|
| 1. 定义问题 | 确认代码、`as_of`、财报期、长期和短期窗口 | 研究问题与完成标准 | 公司无法唯一识别时先澄清 |
| 2. 预注册假设 | 写基准、乐观、悲观假设及证伪条件 | 假设表 | 不允许看完结果后悄悄移动标准 |
| 3. 建立事实底稿 | 原始披露优先，补第二独立来源 | 来源表与未核验字段 | 关键字段单源时降低置信度 |
| 4. 判断公司质量 | 商业模式、护城河、管理层、资本配置、财务质量 | 质量门结论与反证 | 质量门失败则不以“便宜”为买入理由 |
| 5. 完成精确估值 | 三情景、敏感性、安全边际 | 估值区间与关键输入 | 输入不可审计时不给精确目标价 |
| 6. 研究短期环境 | TradingAgents 角色证据 + 最小必要 Vibe 数据 | 市场、资金、政策和事件信号 | 数据不新鲜或窗口未结束时标低置信度 |
| 7. 辩论与裁决 | Bull、Bear、Risk Reviewer 独立审视 | 共识、分歧、冲突矩阵 | 多数投票不能替代证据优先级 |
| 8. 跟踪与审计 | 定义催化剂、失效条件、观察指标并运行审计 | 一页结论、完整报告、审计状态 | 审计未通过时不得称为可发布报告 |

### 五条防偏差纪律

1. **先事实后叙事**：先锁定 `as_of` 和可验证数据，再让 Bull/Bear 解释。
2. **主动寻找反证**：Bear 和 Risk Reviewer 必须尝试推翻基准论文，而不是换一种方式重复它。
3. **禁止信息穿越**：行情、财报、回测和事件都只能使用当时可获得的数据。
4. **禁止精度幻觉**：估值输入质量不足时输出区间和敏感性，不输出虚假的小数点精度。
5. **保留数据缺口**：无法解释的冲突和缺失字段进入待验证清单，不能由 Agent 猜测补全。

## 使用方法

### 用户需要提供什么

最低只需提供公司名或 A 股代码以及想回答的问题。其余字段都有安全默认值：

| 输入 | 是否必需 | 默认值或说明 |
|---|---|---|
| 公司/代码 | 必需 | 支持公司名或 `600519.SH`、`000001.SZ`；歧义时才追问 |
| 研究目标 | 建议 | 未指定时执行标准融合研究 |
| 截止日期 | 可选 | 最近一个已完成交易日，避免使用未收盘数据 |
| 深度 | 可选 | 默认 `3`；可选 `1`、`3`、`5` |
| 重点议题 | 可选 | 护城河、管理层、估值、资金、政策、解禁等 |
| 估值假设 | 可选 | 未指定时由事实底稿推导并披露 |
| 回测 | 可选且需明确授权 | 默认不运行会执行本地策略代码的 Vibe 回测 |
| 输出 | 可选 | 默认生成一页结论和 Markdown 完整报告 |

通用提示词模板：

```text
使用 tradingagents-astock 研究 <公司名或代码>。
目标：回答 <长期价值 / 财报重审 / 当前买入时点 / 异动原因 / 持仓跟踪>。
截至 <YYYY-MM-DD 或最近已完成交易日>，深度 <1 / 3 / 5>。
重点检查 <议题>；默认 Codex-native，只读，不运行回测。
请区分事实、解释、短期信号和最终判断，分别给出长期与短期结论，
列出反证、失效条件、数据缺口、执行模式和审计结果。
```

### 如何选择深度

| 深度 | 适合场景 | 预期结果 |
|---|---|---|
| `1` | 第一次接触公司、异动快速分诊、判断是否值得继续 | 核心事实、最大多空分歧和显著风险；不是完整估值报告 |
| `3` | 默认公司研究、财报后重审、买入时点评估 | 完整双源底稿、三组角色、三情景估值、冲突矩阵和审计 |
| `5` | 高争议公司、拟建立重要投资论文、关键假设重建 | 更长历史、同业对照、强化反证、估值敏感性和风险审查 |

深度代表研究强度，不代表工具数量。即使深度为 `5`，也只调用与问题直接相关的数据工具。

### 按问题选择工作流

| 你想回答的问题 | 推荐调用方式 | 不应省略 |
|---|---|---|
| 公司是否值得长期拥有 | `research` / `investment-research` → `tradingagents-astock` | 护城河反证、资本配置、长期失效条件 |
| 当前是不是合适买点 | `company-valuation` → `tradingagents-astock` → 必要时 `sepa-strategy` | 三道决策门、个人组合假设与短期失效点 |
| 最新财报是否改变论文 | `earnings-review` → `tradingagents-astock` → `thesis-tracker` | 财报原文、预期差、论文变更前后对照 |
| 突然大涨或大跌的原因 | `news-pulse` → `tradingagents-astock` | 事件时间线、价格发生在消息前还是消息后 |
| 多家公司怎么选 | `investment-checklist` / `industry-funnel` → 候选逐家融合研究 | 统一截止日、统一估值口径，避免事后选择 |
| 买入后怎么跟踪 | 读取已有论文 → 增量更新 → `thesis-tracker` | 只更新新信息，不重复全量研究 |

美股、港股和未上市公司不要调用本 Skill。例如研究 Tesla 应使用 `research`、`earnings-review`、`company-valuation`、`investment-checklist` 等通用或美股数据 Skill，再按同样的长期/短期分层方法整合；TradingAgents-astock MCP 只处理 A 股。

### Codex App 快捷入口

运行 `./scripts/install-codex-skills.sh` 并重启 Codex App 后，可以从 Skills 页面选择以下卡片，或在输入框中显式引用：

| App 入口 | 何时使用 |
|---|---|
| `$research` / “AI Berkshire 投研路由” | 不确定工作流时，让路由表自动判断 |
| `$tradingagents-astock` / “A股融合研究” | 已确认需要 A 股多空、资金、政策与长期价值融合 |
| `$earnings-review` / “财报精读” | 财报事实、预期差和论文变化优先 |
| `$investment-checklist` / “买入前检查” | 判断公司质量、估值和买入前风险 |
| `$news-pulse` / “公司异动归因” | 先解释突然大涨大跌或事件冲击 |
| `$thesis-tracker` / “投资论文跟踪” | 将本次结论转成买入后的观察指标 |

推荐先使用 `$research`。只有已经知道所需工作流时，才直接选择具体卡片。`/prompts:*` 是已弃用的 CLI/IDE 兼容入口，不是 Codex App 主入口。

### 当前是否适合买入：推荐问法

```text
研究 600519.SH 当前是否是合适的买入研究窗口，截至最近一个已完成交易日，深度 3。
请依次判断：
1. 公司质量门是否通过，护城河和管理层有哪些可验证反证；
2. 悲观、基准、乐观价值区间及当前安全边际；
3. 未来 20—60 个交易日的资金、事件、政策和流动性风险；
4. 长期结论与短期信号是否冲突；
5. 什么价格、事实或信号会改变结论。
只做研究，不读取账户、不运行回测、不执行交易。
```

若要讨论仓位，需要额外提供可投资资产规模、现有持仓、最大可承受回撤、投资期限和流动性需求。缺少这些信息时只能评价公司与价格，不能给出个性化仓位。

### 系统实际会怎么执行

```text
解析公司和目标
  → 锁定 as_of 与研究成功标准
  → 原始披露 + 第二来源建立事实底稿
  → 商业质量和三情景估值
  → TradingAgents 三组证据角色
  → Vibe 最小工具集验证市场与资金
  → Bull / Bear / Risk Reviewer 反证
  → 长期与短期冲突裁决
  → 一页式结论 + 完整报告 + 审计
```

正常情况下，用户不需要看到或填写 `prepare_codex_native_research` 的底层参数，也不需要手动触发子代理。Skill 负责路由，MCP 负责受控能力，主代理负责等待、去重、计算、裁决和交付。

### 如何阅读最终报告

先看一页式摘要，不要直接跳到某个 Agent 的“买入/卖出”措辞：

1. 确认 `as_of` 日期、财报期和执行模式。
2. 查看三道决策门是否分别通过，不把“好公司”误读为“好买点”。
3. 检查价值区间的关键假设和敏感性，而不是只看目标价。
4. 查看长期结论与短期信号是否冲突，以及各自的失效条件。
5. 检查来源表、单源字段、低置信度结论和报告审计状态。
6. 将催化剂与失效条件加入 `thesis-tracker`，而不是依赖一次性结论。

## 五分钟快速开始

### 1. 确认 Skill 与 MCP 可用

在仓库中同步并检查 Skill：

```bash
python3 scripts/sync-codex-skills.py --check
codex mcp get tradingagents-astock
```

如果 Codex Skill 尚未安装到本机，执行：

```bash
./scripts/install-codex-skills.sh
```

安装后重启 Codex，使新 Skill 被发现。MCP 未注册时按后文[安装](#安装)和[注册 stdio MCP](#注册-stdio-mcp)操作。

### 2. 选择最短提示词

标准融合研究：

```text
使用 tradingagents-astock 研究 600519.SH，深度 3，
默认 Codex-native，完成多空辩论、资金面验证、三情景估值和报告审计。
```

快速判断是否值得深入：

```text
快速研究宁德时代，先做 AI Berkshire 基本面底稿，
再用 tradingagents-astock 验证最近一个交易日的市场、资金和政策风险。
```

财报后重审：

```text
精读比亚迪最新财报，并用 tradingagents-astock 检查财报后资金、市场和多空分歧；
分别给出长期论文是否变化、短期信号及各自失效条件。
```

已持有后的论文跟踪：

```text
更新我对贵州茅台的投资论文：先核验最新公告，
再用 tradingagents-astock 检查短期风险，最后生成 thesis-tracker 观察清单。
```

### 3. 检查交付物

正常产物保存在：

```text
reports/{公司名}/{公司名}-fusion-{YYYYMMDD}.md
```

报告至少应回答四件事：

1. 长期是否值得拥有，估值与安全边际是多少。
2. 短期市场、资金和事件信号是什么，何时失效。
3. 长期与短期是否冲突，最终如何裁决。
4. 哪些关键数据已双源核验，哪些仍是单源或低置信度。

## 架构与边界

```text
Codex / Claude / MCP client
  ├── AI Berkshire skills              最终编排、价值判断、精算、审计
  ├── tradingagents-astock MCP         Codex-native 角色计划 / 可选上游异步图
  ├── Vibe-Trading MCP                 行情、因子、资金流、回测
  └── Longbridge MCP                   结构化行情、公司、财报、估值
            ↓
      原始披露 / 第二独立来源           事实交叉验证
```

TradingAgents-astock 的结论是研究观点，不是独立财务数据源，也不能直接驱动交易。它使用的腾讯、东方财富、新浪、同花顺等聚合数据必须继续与公司公告、交易所或巨潮资讯核验。

数据和观点的优先级如下：

```text
公司/交易所/巨潮原始披露
  → 另一独立来源核验的结构化事实
  → financial_rigor.py 精确计算
  → Vibe-Trading 可复现的行情、资金或回测证据
  → TradingAgents 多角色观点
  → AI Berkshire 综合判断
```

Longbridge、Vibe-Trading、TradingAgents 各自内部无论调用多少工具，最多都只算一个聚合来源；若底层引用相同供应商或公告，彼此也不能构成双源验证。

## 如何组合其他股票 Skill

不要每次把所有 Skill 全部跑一遍。先用研究意图选择主 Skill，再按缺口追加一到两个专用 Skill：

| 用户问题 | 主 Skill | 与 TradingAgents 的组合方式 |
|---|---|---|
| 公司值不值得长期研究 | `research` / `investment-research` | 只有需要市场、资金、多空或政策验证时才追加 |
| 最新财报好不好 | `earnings-review` | 财报事实先行，TradingAgents 解释市场分歧 |
| 为什么突然大涨或大跌 | `news-pulse` | 先建立事件时间线，再检查资金和情绪 |
| 护城河或管理层是否可靠 | `investment-research` / `management-deep-dive` | TradingAgents 只补反方观点和事件风险 |
| 多家公司比较 | `investment-checklist` | 先筛到少数候选，再逐家做融合研究 |
| 当前是否适合买入 | `investment-checklist` / `company-valuation` | 长期价值完成后，用 `sepa-strategy` 检查入场环境 |
| 已持有、买入后跟踪 | `thesis-tracker` / `portfolio-review` | 将市场和政策信号转成论文失效条件 |
| 行业或产业链机会 | `industry-research` / `industry-funnel` | 先确定产业链位置，再对候选 A 股融合研究 |

`research` 可以作为统一入口。只写公司名时默认做标准公司研究；当输入同时包含 A 股以及“多空辩论、资金面、量化验证、回测、三套框架融合”等意图时，自动路由到 `tradingagents-astock`。

### 典型组合顺序

长期研究与短期验证：

```text
research
  → financial-data 双源核验
  → investment-research / company-valuation
  → tradingagents-astock 多角色与市场验证
  → AI Berkshire 冲突裁决
```

财报后复盘：

```text
earnings-review
  → news-pulse（有明显异动时）
  → tradingagents-astock
  → thesis-tracker（已有投资论文时）
```

技术或资金信号不能直接覆盖价值结论。例如“长期低估、短期资金转弱”应输出为两个并存结论，并分别注明时间窗口和失效条件，而不是简单平均成“中性”。

## 完整使用示例

以下以 `600519.SH` 为例。

### 第一步：提交用户请求

```text
使用 tradingagents-astock 对 600519.SH 做标准深度融合研究。
研究日期取最近一个已完成交易日，深度 3；默认 Codex-native。
重点回答：商业质量是否变化、当前估值是否有安全边际、
短期资金与政策风险是什么，以及长期与短期结论是否冲突。
```

### 第二步：系统准备角色计划

适配器先执行健康检查，再以以下等价参数准备计划：

```text
ticker="600519.SH"
trade_date="最近一个已完成交易日，YYYY-MM-DD"
analysts=["market", "social", "news", "fundamentals", "policy", "hot_money", "lockup"]
research_depth=3
```

Codex-native 返回值必须包含：

```text
execution_mode=codex_native
requires_external_llm_credentials=false
upstream_graph_executed=false
```

### 第三步：分层研究

1. AI Berkshire 获取原始财报、公告和第二独立来源，建立基本面底稿。
2. 三个只读证据角色分别研究基本面、市场资金、新闻政策事件。
3. Bull、Bear、Risk Reviewer 基于证据进行第二轮审视。
4. Vibe-Trading 只调用与问题相关的行情、资金、融资融券、解禁或新闻工具。
5. `financial_rigor.py` 验算市值、估值和三情景结果。
6. 主代理制作冲突矩阵并形成最终判断。

### 第四步：检查报告摘要

合格的摘要应明确分层：

```text
长期价值结论：结论、估值区间、核心假设、论文失效条件
短期市场信号：方向、时间窗口、证据、信号失效条件
融合判断：一致 / 冲突 / 数据不足
研究置信度：高 / 中 / 低，以及降级原因
执行模式：Codex-native；未运行原版上游 TradingAgentsGraph
```

### 第五步：审计

```bash
python3 tools/report_audit.py extract \
  --report reports/贵州茅台/贵州茅台-fusion-YYYYMMDD.md
python3 tools/report_audit.py verdict \
  --results '<核验结果>' \
  --report reports/贵州茅台/贵州茅台-fusion-YYYYMMDD.md
```

若缺少原始披露或第二来源，报告必须标记“单源待核验”，不能把 TradingAgents、Vibe 或 Longbridge 的多个工具拼成虚假的双源验证。

## 安装

适配器和上游必须分别使用两个独立环境。TradingAgents-astock 的 `mootdx` 依赖旧版 `httpx`，而当前 MCP 需要新版 `httpx`，不能安全地安装在同一个虚拟环境中：

```bash
cd ~/ai-berkshire/services/tradingagents_astock_mcp
uv sync --extra dev
uv run tradingagents-astock-mcp --help

uv venv ~/.local/share/tradingagents-astock/venv --python 3.12
uv pip install \
  --python ~/.local/share/tradingagents-astock/venv/bin/python \
  'git+https://github.com/simonlin1212/TradingAgents-astock.git@531176ac3161ca13db263495c18b8e0f09fc0eb2'
```

第一个环境只运行 MCP 适配器，不安装 TradingAgents；第二个环境只运行隔离 worker，不安装 MCP。固定 commit `531176ac3161ca13db263495c18b8e0f09fc0eb2` 对应上游 `v0.2.21`。升级前先阅读上游 release notes，并重新运行服务测试，不要直接跟随 `main`。Google/Gemini 的可选 extra 默认不安装。

## 两种执行模式

### 默认：Codex-native

Codex-native 模式不配置额外模型。`prepare_codex_native_research` 只校验请求并返回 TradingAgents 风格的证据角色和辩论计划；Codex App 使用当前对话选择的模型执行，并让未指定模型的原生子代理继承父对话设置。此模式必须披露 `upstream_graph_executed=false`，不能声称运行了原版 TradingAgentsGraph。

Codex 当前公开的 MCP host 能力包括工具、stdio/HTTP、认证和 server instructions，没有公布 MCP sampling 支持，因此 MCP 服务不能反向借用当前对话模型。Codex-native 模式把模型编排留在客户端完成。参见 [Codex MCP 文档](https://developers.openai.com/codex/mcp/) 与 [Codex Subagents 文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)。

### 可选：原版 upstream graph

只有明确需要执行原版 `TradingAgentsGraph` 时，才在启动 MCP 的本地环境中配置模型。不要把凭证写进仓库、命令参数、MCP tool 参数或研究报告：

```bash
export TRADINGAGENTS_LLM_PROVIDER=openai
export TRADINGAGENTS_DEEP_MODEL='your-deep-model'
export TRADINGAGENTS_QUICK_MODEL='your-quick-model'
export OPENAI_API_KEY='在本地安全注入'
```

也可使用上游支持的 Anthropic、DeepSeek、Qwen、MiniMax、GLM、OpenRouter、Ollama 或兼容服务；对应 API Key 沿用 provider 原生环境变量。Google/Gemini 依赖上游可选 extra，当前适配器默认环境未安装该 extra。适配器的 `health_check` 只返回是否就绪，不回显 secret。

可选运行参数：

| 环境变量 | 默认值 | 说明 |
|---|---:|---|
| `TRADINGAGENTS_MCP_DATA_DIR` | 用户本地数据目录 | 任务状态、裁剪后结果和隔离运行目录 |
| `TRADINGAGENTS_MAX_CONCURRENT` | `1` | 最大并发；上游含进程级全局状态，建议保持 1 |
| `TRADINGAGENTS_WORKER_PYTHON` | `~/.local/share/tradingagents-astock/venv/bin/python` | TradingAgents 独立 worker 的 Python 解释器；仅在服务端配置 |
| `TRADINGAGENTS_LLM_PROVIDER` | 适配器默认值 | 仅 upstream graph；服务端固定 provider，客户端不能逐次覆盖 |
| `TRADINGAGENTS_DEEP_MODEL` | 适配器默认值 | 深度推理模型 |
| `TRADINGAGENTS_QUICK_MODEL` | 适配器默认值 | 快速推理模型 |

## 注册 stdio MCP

先取得 `uv` 和仓库的绝对路径：

```bash
command -v uv
cd ~/ai-berkshire && pwd
```

将下列占位符替换为输出的绝对路径：

```bash
codex mcp add tradingagents-astock -- \
  /ABSOLUTE/PATH/TO/uv run \
  --project /ABSOLUTE/PATH/TO/ai-berkshire/services/tradingagents_astock_mcp \
  tradingagents-astock-mcp serve --transport stdio
codex mcp get tradingagents-astock
```

本地集成优先 stdio。若确需 Streamable HTTP：

```bash
cd ~/ai-berkshire/services/tradingagents_astock_mcp
uv run tradingagents-astock-mcp serve --transport http
```

HTTP 只应监听 loopback；不要直接暴露到公网。

## MCP 工具

| 工具 | 用途 |
|---|---|
| `health_check` | 分别返回 Codex-native 与 upstream graph 就绪状态 |
| `prepare_codex_native_research` | 零额外凭证；校验输入并返回供当前 Codex 模型执行的角色计划 |
| `start_astock_research` | 可选 upstream graph；启动隔离研究任务并返回 `run_id` |
| `get_astock_research_status` | 查询 `queued/running/completed/failed` 和阶段信息 |
| `get_astock_research_result` | 返回裁剪后的稳定 JSON，不暴露 LangChain 对象或完整内部状态 |
| `list_astock_research_runs` | 列出最近任务及状态 |

标准结果保留 signal、数据质量摘要、角色报告、投资/交易计划、风险辩论、最终决策、warnings 和上游版本。一次完整运行预计有 30–50 次 LLM 调用；客户端应轮询状态，不要因短超时重复创建任务。

## 验收

无模型凭证时验证 Codex-native 计划、catalog、输入校验和健康状态：

```bash
cd ~/ai-berkshire/services/tradingagents_astock_mcp
uv run pytest
uv lock --check
uv run tradingagents-astock-mcp --help
~/.local/share/tradingagents-astock/venv/bin/python -c \
  'import importlib.metadata as m; print(m.version("tradingagents-astock"))'
codex mcp get tradingagents-astock
```

在新的 Codex 任务中直接执行：

```text
使用 tradingagents-astock 对 600519.SH 做标准深度融合研究。
使用 Codex-native 模式和当前对话模型，不配置额外 Provider；
Vibe-Trading 做只读行情和资金流验证，AI Berkshire 负责双源核验、估值和最终结论。
```

验收时确认：

- MCP 未暴露 order、broker、account、shell、path、endpoint 或 credential 参数。
- Codex-native 返回 `requires_external_llm_credentials=false`，报告披露未运行上游图。
- 相同任务没有因轮询而重复启动。
- 失败任务返回可审计错误，不留下“空报告成功”。
- 输出记录版本、参数、时间、数据质量和缺失字段。
- 报告仍经 `financial_rigor.py` 和 `report_audit.py`。

## 常见问题与排错

| 现象 | 常见原因 | 处理方式 |
|---|---|---|
| Codex 找不到 `tradingagents-astock` Skill | 生成物未同步或安装后未重启 | 运行 `python3 scripts/sync-codex-skills.py --check`；必要时执行安装脚本并重启 Codex |
| 找不到 MCP 工具 | MCP 未注册或路径占位符未替换 | 执行 `codex mcp get tradingagents-astock`，重新检查 `uv` 与仓库绝对路径 |
| `codex_native` 可用但 upstream 不可用 | 未配置上游独立 Provider；这是默认允许状态 | 继续使用 Codex-native，不要为了“完整”索取或传递 API Key |
| `research_depth` 校验失败 | 传入了 `2`、`4` 等非法值 | 只使用 `1`、`3` 或 `5` |
| ticker 校验失败 | 代码与交易所后缀不匹配 | 使用六位 A 股代码；例如 `600519.SH`、`000001.SZ`、`430047.BJ` |
| 报告有观点但没有证据 | 角色只返回结论，或来源字段缺失 | 要求每条 claim 同时给 evidence、source、as-of、confidence、counterevidence 和 gaps |
| 不同数据源数值冲突 | 报告期、复权、币种、GAAP 口径或底层供应商不同 | 优先回到原始披露；记录两个值及误差，不强行平均 |
| 当日信号不完整 | 交易尚未结束或数据源未收盘 | 改用最近一个已完成交易日，并标记不含未完成行情 |
| upstream 任务长时间运行 | 原版图调用多、并发限制为 1 | 使用同一 `run_id` 查询状态；不要重复启动任务 |
| 回测工具不可用 | 默认 allowlist 未开放，或尚未授权本地代码执行 | 先审查策略、区间、运行目录、手续费和前视偏差，再对本次运行单独授权 |

### 为什么默认选择 Codex-native？

它直接使用当前 Codex 对话模型和继承该设置的原生子代理，不需要额外模型账户；请求校验、研究角色和安全边界仍由 MCP 适配器提供。必须如实披露它没有运行原版 `TradingAgentsGraph`。

### 什么时候使用 upstream graph？

仅在需要复现或比较上游 TradingAgentsGraph 行为，且独立 Provider 已在服务端安全配置时使用。普通投资研究不需要它。

### 可以用于美股或港股吗？

不可以。本适配器对 A 股代码和交易所后缀做严格校验。美股、港股使用 `research`、`investment-research`、`earnings-review`、`company-valuation`、`yfinance-data` 等对应 Skill。

### 可以直接给出买卖操作吗？

可以输出研究结论、估值区间、风险、催化剂和失效条件，但不能下单、连接账户或把 Agent 信号自动转成交易。需要讨论仓位时，必须结合用户的风险承受能力和组合约束，并保持为研究建议。

### 为什么多个 MCP 不能自动满足双源验证？

MCP 是接口，不代表底层数据独立。Longbridge、Vibe 和 TradingAgents 可能引用相同公告或相同聚合商。只有确认数据血缘不同，且至少一条为公司、交易所或巨潮原始披露时，才能称为独立核验。

## 更新与卸载

```bash
cd ~/ai-berkshire/services/tradingagents_astock_mcp
uv sync --upgrade
uv run pytest

uv pip install \
  --python ~/.local/share/tradingagents-astock/venv/bin/python --upgrade \
  'git+https://github.com/simonlin1212/TradingAgents-astock.git@531176ac3161ca13db263495c18b8e0f09fc0eb2'

codex mcp remove tradingagents-astock
```

移除 MCP 注册不会自动删除本地运行记录。删除记录前先确认路径和保留要求。

## 许可证与风险

- TradingAgents-astock 为 Apache-2.0，并含上游 `NOTICE`；本仓库不复制其源码，通过固定版本依赖运行。
- Vibe-Trading v0.1.12 为 MIT，标记为 Beta。
- Vibe 的 `backtest` 会执行本地 `signal_engine.py` 且保留数据下载网络能力，不属于纯只读调用；仅在审查代码、隔离运行目录并获得用户明确授权后执行。
- 第三方网页数据可能限流、改版或存在口径差异；开源许可证不等于获得外部数据的再分发权。
- 本项目只供学习与研究，不构成投资建议。
