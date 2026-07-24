---
name: tradingagents-astock
description: 对 A 股公司执行 TradingAgents 多角色辩论、Vibe-Trading 行情与资金面验证、AI Berkshire 基本面与估值融合研究。用户提到 A 股多空辩论、技术面、资金流、政策事件、解禁、游资、因子、回测、交易信号与长期价值冲突，或明确要求 TradingAgents、Vibe-Trading 与 AI Berkshire 联合研究时使用。默认运行只读 Codex-native 模式；不用于美股/港股、实盘下单、账户操作或自动交易。
---

## Codex adapter note

This skill is generated from `skills/tradingagents-astock.md` so Claude Code and Codex users share one canonical workflow.

- Treat `$ARGUMENTS` as the user's request in the current Codex thread.
- When the source mentions Claude-only surfaces such as Task, Agent, WebSearch, Bash, Read, or Write, use the closest Codex capability available in this session: subagents when available, web search when needed, shell commands for local tools, and normal file edits for workspace files.
- Use shared project tools from `tools/` in this repository. Commands that reference `~/ai-berkshire/tools/...` assume the repo is checked out at `~/ai-berkshire`; if needed, prefer the current workspace path.
- Preserve the research quality rules from `AGENTS.md`: cross-check financial data, use exact arithmetic tools for valuation/math, and clearly label uncertainty and source gaps.

# A 股融合研究：TradingAgents × Vibe-Trading × AI Berkshire

使用 TradingAgents-astock MCP、Vibe-Trading MCP 和 AI Berkshire 对 $ARGUMENTS 执行只读 A 股研究。默认采用 `codex_native` 模式：由当前 Codex 对话模型和继承该模型的原生子代理执行 TradingAgents 角色流程，不需要另配 LLM Provider、模型名或 API Key。AI Berkshire 始终是最终编排与结论层；Agent 观点是待验证证据，不是交易指令。

## 适用范围

- A 股上市公司或标准代码，例如 `600519.SH`、`000001.SZ`
- 用户要求“多空辩论”“技术面/资金面验证”“回测”或“三套框架融合”
- 不适用于实盘下单、账户操作、自动交易或未上市公司

若用户只给公司名，先解析为六位代码和交易所。无法唯一识别时才要求补充。

## 默认参数与模式选择

用户没有指定时采用：

| 参数 | 默认值 |
|---|---|
| 执行模式 | `codex_native` |
| 研究日期 | 最近一个已完成交易日 |
| 研究深度 | `3` |
| 分析角色 | `market, social, news, fundamentals, policy, hot_money, lockup` |
| 语言 | 中文 |
| 文件 | `reports/{公司名}/{公司名}-fusion-{YYYYMMDD}.md` |

按问题调整工作流，不要机械调用全部能力：

| 用户意图 | 主工作流 | 追加 Skill |
|---|---|---|
| 标准融合、多空辩论、资金面验证 | 本 Skill 全流程 | `research`、`financial-data` |
| 最新财报是否改变逻辑 | 先做财报事实层，再做融合研究 | `earnings-review` |
| 突发异动、政策或事件归因 | 先确定事件时间线，再做市场辩论 | `news-pulse` |
| 管理层或治理是核心争议 | 加深人的因素，不重复完整基本面 | `management-deep-dive` |
| 比较多个 A 股候选 | 先统一口径筛选，再对少数标的融合研究 | `investment-checklist` |
| 已持有后的持续跟踪 | 把结论转成可观察指标与失效条件 | `thesis-tracker`、`portfolio-review` |
| 入场时点或趋势确认 | 长期结论完成后另做技术验证 | `sepa-strategy` |

若用户仅要求普通公司研究，不含交易、资金、辩论或量化意图，使用 `research`，不要强行调用本 Skill。美股和港股使用对应的 AI Berkshire、财报、估值和行情 Skill；不得把本 MCP 的 A 股能力套用到其他市场。

## 研究方法论

采用“**双时钟、四层证据、三道决策门**”框架。先建立事实底稿，再允许角色辩论；不得从股价走势或 Agent 观点反推基本面事实。

### 双时钟：长期价值与短期市场分开研究

| 时钟 | 核心问题 | 主要证据 | 典型失效条件 |
|---|---|---|---|
| 长期，通常 3—5 年 | 公司是否值得拥有，护城河和内在价值是否增长 | 原始披露、财务报表、产业结构、管理层、资本配置、估值 | 护城河削弱、单位经济恶化、治理失信、估值假设失效 |
| 短期，通常数日到数月 | 当前市场在交易什么，资金、事件和价格是否支持入场 | 行情、成交、资金流、政策、新闻、解禁、情绪、可复现因子 | 催化剂证伪、资金反转、价格结构破坏、事件窗口结束 |

只允许在最终“融合判断”中连接两个时钟。短期走弱不自动否定长期价值，长期优质也不等于当前价格或入场时点合适。

### 四层证据：事实、解释、信号、决策

| 层 | 内容 | 质量要求 |
|---|---|---|
| 事实层 | 收入、利润、现金流、股份数、价格、公告、事件日期 | 记录来源、时间戳、报告期、币种和单位；关键事实至少双源核验 |
| 解释层 | 商业模式、护城河、管理层、周期位置、事件影响 | 明确假设和因果链，保留反证，不把观点写成事实 |
| 信号层 | 动量、量价、资金流、情绪、政策和催化剂 | 写明频率、窗口、复权口径、样本、有效期与失效条件 |
| 决策层 | 值得研究、观察、等待验证、风险上升、论文失效 | 同时引用质量、估值、时点和风险，不由单一指标直接推出 |

每条重要结论按 `claim → evidence → source → counterevidence → confidence → gaps` 记录。来源数量不等于来源独立性；共享底层供应商或同一公告只能算一条证据链。

### 三道决策门：好公司、好价格、好时点

依次判断，不得跳步：

1. **公司质量门**：商业模式是否可理解，护城河是否可验证，管理层和资本配置是否可信，财务质量是否支持叙事。
2. **估值安全边际门**：用可审计输入完成悲观、基准、乐观三情景；检查当前价格相对内在价值区间的安全边际和敏感性。
3. **时点与风险门**：检查市场结构、资金、事件、政策和流动性；它只调整研究优先级、等待条件和入场风险，不改写内在价值。

若质量门不通过，停止讨论“便宜”；若质量通过但安全边际不足，结论为等待价格；若前两门通过但短期信号不利，同时输出长期吸引力与短期等待条件。只有数据充分时才给出高置信度判断。

### 标准研究闭环

1. 定义标的、`as_of` 日期、用户问题、长期和短期时间窗。
2. 写出基准、乐观、悲观假设及各自可证伪条件，避免看完数据后移动标准。
3. 建立原始披露优先的事实底稿，标记未核验字段和数据血缘。
4. 研究商业模式、护城河、管理层、资本配置和财务质量，先过公司质量门。
5. 使用精确工具完成估值和敏感性分析，再过估值门。
6. 使用 TradingAgents 与最小必要的 Vibe 工具研究市场、资金、政策和事件，形成 Bull、Bear、Risk Reviewer 三方意见。
7. 按证据优先级处理冲突，分别输出长期结论、短期信号、融合判断和置信度。
8. 把催化剂、风险和失效条件转成可追踪指标；运行报告审计，保留数据缺口。

## 使用方法

用户不需要手动调用 MCP。根据自然语言识别公司、目标和研究深度；只有标的无法唯一识别、明确要求上游图但环境未就绪、或需要执行本地回测时才询问。

推荐提示词结构：

```text
使用 tradingagents-astock 研究 <公司名或代码>。
研究目标：<长期价值 / 财报重审 / 买入时点 / 异动归因 / 持仓跟踪>。
截至：<日期或最近已完成交易日>；深度：<1 / 3 / 5>。
重点：<护城河、估值、资金、政策、解禁等>。
要求：区分长期与短期，列出反证、失效条件、数据缺口和审计结果。
```

按任务选择深度：

| 深度 | 用途 | 执行范围 |
|---|---|---|
| `1` | 快速分诊、判断是否值得继续研究 | 核心事实、主要多空分歧、显著风险；不假装完成深度估值 |
| `3` | 默认标准研究、财报后重审、买入时点评估 | 完整事实底稿、三组证据角色、三情景估值、冲突矩阵和审计 |
| `5` | 高争议、高仓位意向或论文重建 | 扩展历史和同业比较、强化反证、敏感性与风险审查；不等于自动调用全部工具 |

执行时遵守以下路由：

- “值不值得长期持有”先运行 `research` / `investment-research`，再用本 Skill 补短期证据。
- “当前是否适合买入”必须分别回答公司质量、价格安全边际和时点风险；需要时追加 `company-valuation` 与 `sepa-strategy`。
- “财报是否改变逻辑”先运行 `earnings-review`，再检查市场如何定价新信息。
- “为什么突然涨跌”先运行 `news-pulse` 建立事件时间线，再验证资金和情绪。
- “买入后如何跟踪”完成融合结论后追加 `thesis-tracker`；不要重复整套研究。

交付时先给一页式结论，再链接完整报告。摘要必须包含：`as_of` 日期、长期结论、估值区间与安全边际、短期信号、三道门结果、关键反证、失效条件、置信度、未核验字段、执行模式和审计状态。

## 组件职责

| 层 | 负责 | 不负责 |
|---|---|---|
| AI Berkshire | 商业模式、护城河、管理层、财务质量、估值、双源验证、最终结论、报告审计 | 伪造实时数据、替第三方补全失败结果 |
| TradingAgents-astock MCP | 校验研究请求并准备 Codex-native 角色计划；可选运行原版上游图 | 独立数据复核、精确估值、最终投资结论、下单 |
| Vibe-Trading MCP | 历史行情、财务/资讯/资金流补充、因子分析、确定性回测 | 最终价值判断、文件写入、Shell、交易连接 |
| Longbridge MCP（可用时） | 带时间戳的结构化行情、公司、财报和估值底稿 | 原始披露替代品、第二独立来源、交易 |

## 执行流程

### 1. 建立 AI Berkshire 基准底稿

先按 `skills/research.md` 和 `skills/financial-data.md`：

1. 记录代码、公司名、研究日期和财报期。
2. 获取 Longbridge 或其他结构化数据底稿。
3. 用交易所公告、巨潮资讯或公司 IR 原始披露交叉验证关键财务数据。
4. 使用 `tools/financial_rigor.py` 验证市值、估值和三情景结果。

先写出本次研究的成功标准：长期要回答“是否值得拥有、什么价格有安全边际”，短期要回答“市场与资金信号是什么、何时失效”。两个时间尺度分开记录，禁止用短期信号替换长期价值判断。

### 2. 执行 TradingAgents 角色研究

先调用 `health_check` 并记录两种模式状态。除非用户明确要求“原版 TradingAgentsGraph”，否则必须选择 `codex_native`。

#### 默认：Codex-native（零额外凭证）

1. 调用 `prepare_codex_native_research`，严格使用以下参数名和枚举，不得把返回的分组角色名当作 analysts：

   ```text
   ticker="600519.SH"
   trade_date="最近一个已完成交易日，YYYY-MM-DD"
   analysts=["market", "social", "news", "fundamentals", "policy", "hot_money", "lockup"]
   research_depth=3
   ```

   `research_depth` 只能是整数 `1`、`3`、`5`；analysts 只能取上述七个原版名称的非空子集。MCP 会把它们编排为下列三个 Codex-native 证据分组。
2. 确认返回 `execution_mode=codex_native`、`requires_external_llm_credentials=false` 和 `upstream_graph_executed=false`。
3. 若原生子代理可用，启动最多 3 个并行只读子代理；不指定 `model` 或 `reasoning_effort`，让它们继承当前 Codex 对话设置：
   - `fundamentals`：商业质量、财务报表、估值输入、来源缺口。
   - `market_flow`：价格、流动性、动量、资金流、融资融券、大宗交易。
   - `news_policy_events`：新闻、情绪、政策、游资、解禁、催化剂与事件风险。
4. 子代理只返回结构化证据和来源，不修改报告或仓库文件。主代理等待三者完成并去重事实。
5. 复用这 3 个子代理做第二轮独立审视：分别形成 Bull、Bear、Risk Reviewer 意见；不得把第一轮结论当作已证实事实。
6. 主代理执行 AI Berkshire 的双源核验、冲突裁决、估值和最终判断。

如果当前客户端没有子代理能力，由主代理依次执行相同角色，不得因此切换到外部 LLM Provider。输出必须明确写明“TradingAgents 角色拓扑由 Codex-native 执行，未运行原版上游 TradingAgentsGraph”。

每个证据角色至少返回以下字段，避免只给观点：

```text
claim: 可检验的结论
evidence: 支撑数据或原文摘要
source: provider、原始 URL/公告、抓取时间、报告期
confidence: high / medium / low
counterevidence: 反例或相反证据
gaps: 尚缺数据
```

Bull、Bear 和 Risk Reviewer 只能引用第一轮证据或明确新增来源。Risk Reviewer 必须检查数据新鲜度、来源独立性、前视偏差、估值敏感性和结论失效条件。

#### 可选：原版 upstream graph

仅当用户明确要求原版引擎，且 `health_check.modes.upstream_graph.status=ready` 时，才依次调用：

1. `start_astock_research` 启动隔离任务。
2. 保存 `run_id` 并轮询 `get_astock_research_status`；不要重复启动相同任务。
3. 完成后调用 `get_astock_research_result`；失败时记录错误和数据缺口，不得伪造角色报告。

此模式需要独立 Provider 配置，不能直接复用当前 Codex 对话模型或 ChatGPT 会话凭证。不得把 API Key、模型 base URL、任意文件路径或命令作为工具参数传入。

提取并保留：

- `signal` 和 `final_decision`
- 数据质量摘要和缺失报告
- 基本面、市场、新闻、情绪等角色报告
- Bull/Bear 争点、研究经理投资计划、交易员计划和风险辩论
- `upstream_version`、运行时间和 warnings

### 3. 使用 Vibe-Trading 做量化验证

Vibe-Trading MCP 只允许使用与当前研究直接相关的只读工具：

- `search_symbol`
- `get_market_data`
- `get_financial_statements`
- `get_stock_profile`
- `get_stock_news`
- `get_research_reports`
- `get_fund_flow`
- `get_dragon_tiger`
- `get_northbound_flow`
- `get_margin_trading`
- `get_block_trades`
- `get_shareholder_count`
- `get_lockup_expiry`
- `get_sector_info`
- `screen_market`
- `get_macro_series`
- `iwencai_search`

按研究问题选择最小工具集：

| 问题 | 优先工具 |
|---|---|
| 趋势、波动、成交与流动性 | `get_market_data` |
| 主力/北向/融资融券/大宗交易 | 对应 fund flow、northbound、margin、block trade 工具 |
| 新闻、政策、催化剂 | `get_stock_news`、`get_sector_info`、`get_macro_series` |
| 解禁、股东变化、游资 | `get_lockup_expiry`、`get_shareholder_count`、`get_dragon_tiger` |
| 卖方预期与市场分歧 | `get_research_reports` |

不要为了“看起来完整”抓取与结论无关的数据。所有行情和资金数据记录交易日、频率、复权口径和数据源。

Codex 的 Vibe MCP 注册应使用 `enabled_tools` allowlist，只开放上述数据工具。以下两个工具不进入默认 allowlist：

- `factor_analysis`：仅在用户明确要求且输入/输出位于本次任务隔离目录时临时开放。
- `backtest`：仅在用户明确授权执行已审查的本地策略代码后临时开放。

Vibe 的 `backtest` 会执行 `signal_engine.py`，不是纯只读工具。调用前必须展示待执行策略、确认运行目录不含敏感文件/凭证，并获得用户对本次本地代码执行的明确授权；未授权时只获取行情，使用仓库内已经审查的确定性工具，或把回测标记为未执行。`factor_analysis` 会读取路径并写出文件，只允许使用本次任务的隔离目录。

回测必须记录标的、区间、频率、策略、基准、手续费/滑点假设和是否存在前视偏差。样本不足或数据源降级时标注低置信度。

永久禁止调用 Vibe-Trading 的 `write_file`、`run_swarm`、Shell、连接器选择、券商、账户或任何交易工具；不得启用 `--enable-shell-tools`。报告文件由 AI Berkshire 在仓库内写入。

### 4. 冲突裁决

按以下顺序处理冲突：

```text
公司/交易所原始披露
  → 经双源验证的结构化事实
  → financial_rigor.py 精确计算
  → 可复现的 Vibe-Trading 回测/因子证据
  → TradingAgents-astock 多角色观点
  → AI Berkshire 最终判断
```

TradingAgents、Vibe-Trading 和 Longbridge 各自内部的多个工具只算各自一个聚合来源。若它们底层引用同一供应商或同一公告，不得算作独立双源。Agent 结论本身不算财务数据来源。

当 TradingAgents 的短期信号与 AI Berkshire 的长期价值结论冲突时，同时保留两者，并分别写明时间尺度、证据和失效条件，不强行平均。

使用冲突矩阵输出最终裁决：

| 议题 | AI Berkshire 长期结论 | TradingAgents/Vibe 短期结论 | 冲突原因 | 裁决与失效条件 |
|---|---|---|---|---|

最终行动语言只允许使用“值得继续研究 / 观察 / 等待验证 / 风险上升 / 论文失效”等研究表述。若给出价格区间或仓位讨论，必须同时列出假设、时间尺度和风险承受前提，不得转化成自动交易指令。

## 输出

保存到：

```text
reports/{公司名}/{公司名}-fusion-{YYYYMMDD}.md
```

至少包含：

1. 执行摘要：长期结论、短期信号、置信度
2. 数据与来源表：时间戳、期间、币种、单位、独立性
3. AI Berkshire 价值研究与三情景估值
4. TradingAgents 多角色共识、分歧和风险辩论
5. Vibe-Trading 行情、因子和回测验证
6. 冲突矩阵：一致项、冲突项、裁决依据
7. 风险、催化剂、失效条件和待验证问题
8. 工具运行记录：版本、参数、`execution_mode`；仅 upstream graph 模式记录 run_id
9. 声明：仅供学习研究，不构成投资建议或交易指令

执行摘要必须把长期与短期拆开：

```text
长期价值结论：结论 + 估值区间 + 核心失效条件
短期市场信号：方向 + 时间窗口 + 证据 + 信号失效条件
融合判断：一致 / 冲突 / 数据不足
研究置信度：高 / 中 / 低，以及降级原因
```

完成后运行：

```bash
python3 tools/report_audit.py extract --report <报告路径>
python3 tools/report_audit.py verdict --results '<核验结果>' --report <报告路径>
```

## 降级策略

- TradingAgents MCP 不可用：由当前 Codex 模型按本 Skill 的同一角色拓扑执行，标记 MCP 请求校验未运行。
- Vibe-Trading MCP 不可用：保留 TradingAgents + AI Berkshire，回测/因子部分标记未验证。
- 两者都不可用：退回 `investment-research`，不得声称完成融合研究。
- upstream graph 缺少模型凭证：自动保留或切回 `codex_native`；不得索取、复制或回显敏感值。
- 数据冲突无法解释：以原始披露为准，结论降置信度并列入待验证问题。
- 原始披露或第二独立来源缺失：可完成角色研究，但关键财务字段标记“单源待核验”，报告不得标为可发布。
- 交易日仍在进行或数据未收盘：改用最近一个已完成交易日，注明未包含当日未完成行情。
- 用户要求美股、港股或未上市公司：切换到 `research` 或相应市场 Skill，不伪装成 A 股融合研究。

## 用户交互规则

- 清晰、安全、只读的请求直接执行，不要求用户先理解 MCP 参数。
- 仅在公司无法唯一识别、用户坚持 upstream graph 但环境未就绪、或用户要求本地回测时询问必要信息或授权。
- 回测授权必须限定本次策略、标的、日期区间、运行目录与代码版本；一次授权不得复用于下一次回测。
- 完成时给出报告路径、执行模式、使用的数据源、审计结果、未验证字段和没有执行的高风险能力。

## 完成标准

- 组件职责没有混淆，AI Berkshire 给出最终结论
- 记录 `execution_mode`；Codex-native 明确披露未运行上游图，upstream graph 才要求 run_id、最终状态和版本
- Vibe 回测/因子参数可复现，或明确记录未执行原因
- 关键财务事实满足双源规则，聚合器没有被伪装成多个独立来源
- 所有计算由精确工具完成，报告通过审计或明确列出未通过项
- 未读取私人账户、未运行 Shell、未写第三方文件、未触发任何交易
