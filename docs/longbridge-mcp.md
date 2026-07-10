# Longbridge MCP 接入指南

## 它在本仓库中的职责

Longbridge 是 AI Berkshire 的**结构化数据获取层**，不是计算层、报告层或交易层。

```text
Longbridge MCP
  │  行情、公司、财报、估值、新闻、股东、机构数据
  ▼
skills/longbridge-data.md
  │  生成带工具名、参数、时间戳和口径说明的数据底稿
  ▼
第二独立来源 / 原始披露
  │  SEC、HKEX、巨潮、公司 IR、独立数据库
  ▼
tools/financial_rigor.py
  │  市值、PE/PB/ROE/FCF Yield、多源误差、三情景估值
  ▼
tools/report_audit.py
  │  报告数据抽检和准出
  ▼
reports/
```

Longbridge 解决的是原来依赖网页抓取时的几个问题：

- 实时行情和盘前/盘后时间戳不统一
- 公司、财报和估值数据散落在不同网站
- 网页结构变化导致抓取失败
- Agent 输出缺少明确的工具参数和数据时间
- 港股、美股、A 股需要不同网站和代码格式

它不解决：

- 原始财报阅读
- 第二独立来源验证
- GAAP / Non-GAAP 口径判断
- 精确估值计算
- 投资决策和交易执行

## Codex 安装

Longbridge 使用远程 Streamable HTTP MCP 和 OAuth 登录。不要把 OAuth token 或账户信息提交到仓库。

```bash
codex mcp add longbridge --url https://mcp.longbridge.com
```

首次添加时 Codex 会启动浏览器 OAuth 授权。如果需要重新授权：

```bash
codex mcp login longbridge
```

检查状态：

```bash
codex mcp get longbridge
codex mcp list
```

预期配置位于用户级 `~/.codex/config.toml`：

```toml
[mcp_servers.longbridge]
url = "https://mcp.longbridge.com"
```

配置和 OAuth 凭证是**用户级运行环境状态**，不进入 Git。仓库通过 Skill 和文档声明如何使用该 MCP，而不是提交个人授权。

完成配置后，重启 Codex 或新建任务，使工具清单重新加载。

## 仓库入口

安装或更新 Codex skills：

```bash
./scripts/install-codex-skills.sh
```

随后可以使用：

```text
使用 research 研究腾讯
使用 longbridge-data 为 AAPL.US 生成公司、财报和估值数据底稿
使用 longbridge-data 获取 700.HK 最近五年财务和业务分部
使用 investment-research 研究腾讯，优先用 Longbridge 取数并执行双源验证
使用 earnings-review 分析 AAPL.US 最新财报，用 Longbridge 做结构化对照
```

日常使用只需要记住 `research`。例如：

```text
/prompts:research 腾讯
/prompts:research 苹果 快速
/prompts:research MSFT.US 最新财报
/prompts:research 腾讯 阿里 美团 对比
```

它会根据自然语言自动路由到完整研究、快速摘要、财报、异动、公司对比或行业筛选，并自动应用本页的数据来源和安全规则。

Claude Code 或其他 MCP 客户端也可连接同一个 URL；具体配置格式由客户端决定。仓库的 canonical workflow 位于 `skills/longbridge-data.md`，客户端只需把工具名称映射到 Longbridge MCP 即可。

## 来源规则

Longbridge 的所有工具合计只算一个第三方来源。例如：

```text
financial_report_latest + financial_statement = 一个 Longbridge 来源
quote + calc_indexes = 一个 Longbridge 来源
valuation + valuation_history = 一个 Longbridge 来源
```

合格的双源组合：

```text
Longbridge + SEC 10-K/10-Q
Longbridge + HKEX 年报/公告
Longbridge + 巨潮资讯年报
Longbridge + 另一家独立财务数据库
```

不合格的双源组合：

```text
Longbridge quote + Longbridge calc_indexes
Longbridge financial_report + Longbridge financial_statement
Longbridge valuation + Longbridge valuation_history
```

## 安全模型

AI Berkshire 的 Longbridge 接入默认是只读研究模式：

1. 不下单、撤单、改单。
2. 不创建、暂停或恢复定投。
3. 不修改提醒、自选股或社区内容。
4. 默认不读取账户余额、持仓、订单、银行卡、入金、出金。
5. 即使工具可见，也不能把工具可见性当成操作授权。

完整禁止清单维护在 `skills/longbridge-data.md`。

## 数据底稿要求

每次 Longbridge 取数至少记录：

- 证券代码和市场
- Longbridge 服务端时间
- 工具名称和参数
- 数据报告期或行情时间戳
- 币种与单位
- 数据口径和缺失字段
- 第二来源验证状态
- 是否读取账户信息
- 是否执行写操作（必须为否）

这使后续报告能够区分：

- 当前行情 vs 历史收盘
- TTM PE vs 静态/预测 PE
- 财年 vs 自然年
- GAAP vs Non-GAAP
- 原始披露 vs 第三方汇总

## 当前验证状态

2026-07-10 的接入验证中，Longbridge MCP 在 Codex 中暴露了 147 个工具。以下只读调用均成功：

- `quote(AAPL.US)`
- `company(AAPL.US)`
- `valuation(AAPL.US)`
- `financial_report_latest(AAPL.US)`

工具数量和返回字段可能随服务升级变化，因此 Skill 不依赖固定工具总数，只依赖具体工具能力和只读安全边界。
