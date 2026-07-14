# Longbridge × AI Berkshire 集成方法总结

## 一句话说明

**Longbridge 负责结构化取数，AI Berkshire 负责研究、交叉验证、精确计算、风险判断和报告准出。**

Longbridge 不是 AI Berkshire 的替代品，也不是第二个独立来源；它是研究链路最前端的实时数据获取层。

## 系统分工

| 组件 | 职责 | 不负责 |
|---|---|---|
| Longbridge MCP | 行情、证券信息、财报、估值、股东、机构、新闻、公告索引 | 原始财报阅读、独立双源验证、最终投资结论 |
| `skills/longbridge-data.md` | 规范 MCP 只读取数、记录时间戳/参数/口径、生成数据底稿 | 精确估值和报告发布 |
| `skills/research.md` | 一键识别公司和任务类型，自动路由研究流程 | 绕过数据验证 |
| `skills/financial-data.md` | 定义来源优先级、双源规则和误差处理 | 获取实时行情 |
| `tools/financial_rigor.py` | 市值、PE/PB/ROE、FCF、多源误差和三情景估值 | 网络取数 |
| `tools/report_audit.py` | 报告数据抽样复核和准出/打回 | 研究判断 |
| `reports/` | 保存可复现研究报告 | 存放 OAuth 凭证或账户数据 |

## 标准数据流

```text
用户只输入：research 公司名
          │
          ▼
skills/research.md
  自动识别证券代码和任务类型
          │
          ▼
Longbridge MCP（只读）
  行情 / 公司 / 财报 / 估值 / 新闻 / 股东
          │
          ▼
skills/longbridge-data.md
  记录工具、参数、时间戳、币种、报告期、缺失字段
          │
          ├──────────────┐
          ▼              ▼
原始披露           第二独立数据源
SEC / HKEX / SSE   独立数据库 / 公司 IR
巨潮 / 公司公告
          │              │
          └──────┬───────┘
                 ▼
tools/financial_rigor.py
  双源误差 / 市值 / 估值 / 情景计算
                 │
                 ▼
AI Berkshire 研究框架
  生意 / 护城河 / 管理层 / 风险 / 行业 / 估值
                 │
                 ▼
tools/report_audit.py
  抽检通过后写入 reports/
```

## 为什么这样接入

### Longbridge 解决的问题

- 实时行情和盘前、盘后、夜盘时间戳不统一。
- 港股、美股、A 股代码和数据入口分散。
- 网页结构变化导致抓取失败。
- 公司、估值、股东、机构和新闻数据缺少统一 schema。
- Agent 容易遗漏数据日期、币种和报告期。

### AI Berkshire 保留的职责

- 读取原始年报、季报和监管公告。
- 判断 GAAP / Non-GAAP、静态 / TTM / 预测口径。
- 把 Longbridge 与第二来源进行交叉验证。
- 使用精确十进制重新计算市值和估值。
- 写出正反论据、失败路径和行动价格带。
- 对最终报告进行数据抽检。

## 最重要的来源规则

**Longbridge 的所有工具合计只算一个第三方来源。**

以下不构成双源：

```text
quote + calc_indexes
financial_report_latest + financial_statement
valuation + valuation_history
```

合格的双源组合：

```text
Longbridge + SEC 10-K/10-Q
Longbridge + HKEX/SSE/巨潮公告
Longbridge + 公司 IR 原始财报
Longbridge + 另一家独立财务数据库
```

如果 Longbridge 与原始披露冲突：

1. 以原始披露为准。
2. 在报告中保留冲突记录。
3. 检查币种、报告期、汇率、TTM、归母/非归母和 GAAP/Non-GAAP 口径。
4. 不得静默选择更符合原有结论的数据。

## 默认安全边界

AI Berkshire 的 Longbridge 接入默认是**只读研究模式**：

- 禁止下单、撤单、改单。
- 禁止创建或修改定投。
- 禁止修改提醒、自选股和社区内容。
- 默认不读取余额、持仓、订单、银行卡、入金和出金。
- 只有用户明确要求分析本人组合时，才允许读取最小必要的账户只读数据。

完整工具禁止清单维护在 `skills/longbridge-data.md`。

## 一键使用

日常只需记住：

```text
research 公司名
```

示例：

```text
research 腾讯
research 苹果 快速
research 小米 最新财报
research 赛力斯 异动
research 腾讯 阿里 美团 对比
research AI算力 筛选
```

Codex slash prompt：

```text
/prompts:research 腾讯
```

`research` 自动路由：

| 输入 | 工作流 |
|---|---|
| 公司名 | `investment-research` |
| 快速/简版 | 快速研究摘要 |
| 财报/年报/季报 | `earnings-review` |
| 异动/大涨/大跌 | `news-pulse` |
| 多公司对比 | `investment-checklist` |
| 管理层/CEO | `management-deep-dive` |
| 行业/筛选 | `industry-research` / `industry-funnel` |
| 持仓/组合 | `portfolio-review` |

## 直接获取 Longbridge 数据底稿

当只需要数据，不需要完整报告：

```text
使用 longbridge-data 为 AAPL.US 生成行情、财报和估值底稿
使用 longbridge-data 获取 700.HK 最近五年财务和业务分部
```

标准底稿至少包含：

- Longbridge 服务端时间。
- 证券代码和市场。
- 调用工具及参数。
- 行情时间或财务报告期。
- 币种和单位。
- 缺失字段和口径风险。
- 第二来源验证待办。
- 是否读取账户信息。
- 是否发生写操作（必须为否）。

## 典型研究工具映射

| 研究问题 | Longbridge 工具 | 后续验证 |
|---|---|---|
| 当前股价、市值、PE/PB | `quote`、`calc_indexes` | 交易所行情、股价×总股本 |
| 公司和证券身份 | `static_info`、`company` | 交易所/公司 IR |
| 最新财报摘要 | `financial_report_latest` | 原始年报/季报 |
| 三张表和财务比率 | `financial_statement`、`financial_report` | SEC/HKEX/SSE/巨潮 |
| 业务结构 | `business_segments` | 年报分部附注 |
| 历史估值 | `valuation`、`valuation_history` | 自行计算利润口径 |
| 分析师预期 | `consensus`、`institution_rating` | 检查更新时间和样本数 |
| 股东和分红 | `shareholder_top`、`dividend` | 交易所权益披露 |
| 新闻和公告 | `news`、`filings` | 打开公告原文确认 |

## 报告准出标准

完整研究至少满足：

- 已确认证券代码和主要上市地。
- Longbridge 数据有明确时间戳和报告期。
- 关键财务数据至少两个独立来源。
- 市值、PE/PB、FCF 等由 `financial_rigor.py` 重算。
- Longbridge 与原始披露的冲突已解释。
- 报告包含反面论据和可观察的失败信号。
- `report_audit.py` 抽检通过，或明确标记未准出。
- 未执行交易、账户写入或社区写入。

## 配置入口

完整的客户端配置、OAuth、区域端点、验证和故障排查参见：

- [`docs/longbridge-mcp.md`](longbridge-mcp.md)
- Longbridge 官方 MCP 文档：https://open.longbridge.com/docs/mcp
