# Longbridge MCP 配置与排障指南

> 文档验证日期：2026-07-14。Longbridge 官方配置发生变化时，以官方 MCP 文档为准：<https://open.longbridge.com/docs/mcp>。

## 1. 服务地址

Longbridge 提供托管式 Streamable HTTP MCP 服务，通过 OAuth 2.1 授权。

| 使用环境 | 地址 |
|---|---|
| 全球默认 | `https://mcp.longbridge.com` |
| 中国大陆加速 | `https://mcp.longportapp.cn` |
| Agent Auth 入口 | 在上述地址后添加 `/agent` |

建议：

- 中国大陆网络优先使用 `https://mcp.longportapp.cn`。
- 其他地区使用 `https://mcp.longbridge.com`。
- 如果 OAuth 浏览器回调不可用，再考虑 `/agent` 的授权码模式。

## 2. 在 AI Berkshire 中的定位

Longbridge 是 AI Berkshire 的**结构化取数层**，不是计算、报告或交易层。

```text
Longbridge MCP
  → skills/longbridge-data.md
  → 原始披露 / 第二独立来源
  → tools/financial_rigor.py
  → AI Berkshire 研究 Skill
  → tools/report_audit.py
  → reports/
```

完整方法说明参见 [`docs/longbridge-ai-berkshire.md`](longbridge-ai-berkshire.md)。

## 3. Codex CLI 配置

### 3.1 添加服务器

全球默认：

```bash
codex mcp add longbridge --url https://mcp.longbridge.com
```

中国大陆：

```bash
codex mcp add longbridge --url https://mcp.longportapp.cn
```

首次添加时 Codex 通常会自动检测 OAuth 并打开浏览器授权。

### 3.2 重新登录

```bash
codex mcp login longbridge
```

### 3.3 查看状态

```bash
codex mcp get longbridge
codex mcp list
```

正常状态示例：

```text
Name        Url                         Status   Auth
longbridge  https://mcp.longbridge.com  enabled  OAuth
```

### 3.4 用户级配置

Codex 将 MCP 地址写入用户级 `~/.codex/config.toml`：

```toml
[mcp_servers.longbridge]
url = "https://mcp.longbridge.com"
```

中国大陆配置：

```toml
[mcp_servers.longbridge]
url = "https://mcp.longportapp.cn"
```

OAuth token 由客户端安全存储，不应手工写入仓库，也不得提交到 Git。

### 3.5 删除和重新配置

```bash
codex mcp logout longbridge
codex mcp remove longbridge
codex mcp add longbridge --url https://mcp.longbridge.com
```

切换全球/大陆端点时，建议先删除旧配置再重新添加并授权。

## 4. Codex Desktop 配置

在 Codex Desktop 中：

1. 打开 **Settings**。
2. 进入 **MCP servers**。
3. 点击添加服务器。
4. 名称填写 `longbridge`。
5. URL 填写：
   - 全球：`https://mcp.longbridge.com`
   - 中国大陆：`https://mcp.longportapp.cn`
6. 保存后点击 **Connect**。
7. 浏览器打开 Longbridge OAuth 页面后完成授权。
8. 新建任务或重启 Codex，让工具清单重新加载。

如果 Desktop 和 CLI 使用同一个 `CODEX_HOME`，通常可以共享用户级 MCP 配置；工具清单是否热更新取决于当前客户端版本，最稳妥的方式是新建任务。

## 5. Claude Code 配置

Longbridge 官方文档给出的 Claude Code 接入方式：

全球默认：

```bash
claude mcp add --transport http longbridge https://mcp.longbridge.com
```

中国大陆：

```bash
claude mcp add --transport http longbridge https://mcp.longportapp.cn
```

确认：

```bash
claude mcp list
```

首次调用 Longbridge 工具时按客户端提示完成 OAuth。

## 6. 通用 MCP 客户端配置

支持 Streamable HTTP 的客户端通常使用：

```json
{
  "mcpServers": {
    "longbridge": {
      "type": "http",
      "url": "https://mcp.longbridge.com"
    }
  }
}
```

中国大陆：

```json
{
  "mcpServers": {
    "longbridge": {
      "type": "http",
      "url": "https://mcp.longportapp.cn"
    }
  }
}
```

具体字段名以客户端为准。有些客户端使用 `transport: "http"`，有些使用 `type: "streamable-http"`。

## 7. OAuth 2.1 授权流程

正常流程：

```text
客户端连接 MCP
  → MCP 返回 OAuth 授权要求
  → 浏览器打开 Longbridge 登录页
  → 用户登录并同意授权
  → 浏览器回调本地客户端
  → 客户端保存 token
  → MCP 工具可用
```

OAuth 授权允许用户在 Longbridge 页面查看和撤销已授权应用。

### 授权注意事项

- 使用与 Longbridge 账户相同的区域和服务环境。
- 不要复制 OAuth token 到 Skill、报告或配置示例。
- 不要将个人账户数据写入 `reports/` 或提交到 Git。
- 工具可见不等于允许执行写操作。

## 8. Agent Auth 授权码模式

当客户端不能打开浏览器、没有可靠回调地址，或自动 OAuth 失败时，可使用官方 Agent Auth 扩展。

连接地址：

```text
https://mcp.longbridge.com/agent
```

中国大陆：

```text
https://mcp.longportapp.cn/agent
```

典型流程：

1. 客户端连接 `/agent`。
2. 调用 MCP 暴露的 `authenticate` 工具。
3. 工具返回授权 URL。
4. 用户在任意浏览器打开 URL 并登录。
5. 页面显示一次性授权码。
6. 将授权码提交给 `authenticate` 工具。
7. 授权成功后，其他工具开始可用。

如果普通 OAuth 正常，不要优先使用 `/agent`。

## 9. 验证连接

### 9.1 配置级验证

```bash
codex mcp get longbridge
codex mcp list
```

必须确认：

- 状态为 `enabled`。
- Auth 为 OAuth 或已认证状态。
- URL 指向正确区域端点。

### 9.2 工具级验证

建议只调用无账户、无副作用的工具：

```text
now
static_info(symbols=["AAPL.US"])
quote(symbols=["AAPL.US"])
company(symbol="AAPL.US")
```

验证成功标准：

- `now` 返回服务端 UTC 时间。
- `static_info` 返回证券名称、交易所和币种。
- `quote` 返回价格和行情时间戳。
- 不出现 OAuth、权限或连接错误。

### 9.3 AI Berkshire 级验证

安装仓库 skills：

```bash
./scripts/install-codex-skills.sh
./scripts/install-codex-prompts.sh
```

重启 Codex 后测试：

```text
使用 longbridge-data 为 AAPL.US 生成最小只读数据底稿
```

一键研究测试：

```text
research 微软 快速
```

## 10. 在仓库中的使用入口

### 只获取数据

```text
使用 longbridge-data 为 700.HK 获取公司、财报和估值底稿
```

### 完整研究

```text
research 腾讯
```

### 财报

```text
research 小米 最新财报
```

### 异动

```text
research 赛力斯 异动
```

### 多公司对比

```text
research 腾讯 阿里 美团 对比
```

## 11. 数据来源规则

Longbridge 的多个工具不能互相构成双源：

```text
financial_report_latest + financial_statement = 一个来源
quote + calc_indexes = 一个来源
valuation + valuation_history = 一个来源
```

关键数据必须与以下至少一种来源交叉验证：

- SEC / HKEX / SSE / SZSE / 巨潮公告。
- 公司 IR 原始财报。
- 另一家独立金融数据供应商。

如果数据冲突，以原始披露为准，并检查：

- 币种和汇率。
- 报告期和财年定义。
- TTM / 静态 / 预测指标。
- 归母 / 总利润。
- GAAP / Non-GAAP。
- 复权、拆股和总股本日期。

## 12. 安全模型

AI Berkshire 默认永久禁止：

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

默认不读取：

- 账户余额。
- 股票或基金持仓。
- 订单和成交。
- 银行卡。
- 入金和出金。
- 个人账户结单。

只有用户明确授权组合分析时，才允许读取最小必要的账户只读工具；仍然禁止交易和写入。

## 13. 常见问题排查

### `codex mcp list` 看不到 longbridge

```bash
codex mcp add longbridge --url https://mcp.longbridge.com
codex mcp list
```

如果仍不存在，检查当前 `CODEX_HOME` 是否与安装时一致。

### 状态 enabled，但当前任务没有工具

MCP 工具列表通常在任务启动时加载：

1. 新建 Codex 任务。
2. 或重启 Codex Desktop/CLI。
3. 再执行 `codex mcp get longbridge`。

### OAuth 页面没有打开

```bash
codex mcp login longbridge
```

如果本地回调失败，改用 `/agent` 授权码模式。

### 中国大陆连接慢或超时

把地址改为：

```text
https://mcp.longportapp.cn
```

不要同时配置两个同名 `longbridge` server。

### `401` / `unauthorized`

```bash
codex mcp logout longbridge
codex mcp login longbridge
```

仍失败时删除并重新添加服务器。

### `403` / 权限不足

可能原因：

- 账户未拥有对应市场行情权限。
- 工具属于账户或交易能力，但 OAuth scope 未授权。
- 某些市场或数据产品需要额外订阅。

先用 `now`、`static_info`、`company` 等基础只读工具确认连接。

### 行情或财务数据口径不一致

不要把它当成连接故障。依次检查：

1. 币种是否被转换。
2. 报告是单季度还是累计值。
3. 利润是归母、总利润还是调整后利润。
4. PE 是静态、TTM 还是预测。
5. 数据更新时间是否一致。

### 工具返回内容过长

- 限制证券数量。
- 缩短历史时间范围。
- 优先请求摘要，再按需请求明细。
- 不要一次拉取全部历史估值、新闻和财务字段。

## 14. 凭证和隐私

不得提交到仓库：

- OAuth token。
- 授权码。
- Longbridge 账户信息。
- 持仓、余额、订单和银行资料。
- 包含上述数据的日志或报告。

仓库只提交：

- MCP 地址。
- 安装和验证命令。
- 只读研究工作流。
- 工具允许/禁止规则。

## 15. 官方能力范围与仓库验证

Longbridge 官方文档描述其提供 100+ 工具，覆盖证券行情、公司基本面、市场洞察、投资组合和交易等能力。

本仓库 2026-07-10 的实测会话暴露了 147 个工具，并成功验证：

```text
now
quote
static_info
company
valuation
financial_report_latest
```

工具总数和字段可能随服务升级变化，因此仓库不依赖固定数量，只依赖具体工具名称、返回口径和安全边界。
