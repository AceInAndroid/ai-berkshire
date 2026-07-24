# AI Berkshire × TradingAgents × Vibe-Trading × Longbridge MCP 环境复刻指南

> 最后核对：2026-07-23。安装命令发生变化时，以各项目官方文档为准。

本文用于在一台新电脑上复刻以下只读投资研究环境：

- [OpenAI Codex](https://developers.openai.com/codex/)
- [AI Berkshire](https://github.com/xbtlin/ai-berkshire)
- [TradingAgents-astock](https://github.com/simonlin1212/TradingAgents-astock) v0.2.21
- [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading)
- [Longbridge MCP](https://open.longbridge.com/docs/mcp)

默认边界是研究、数据获取、估值和回测，不配置真实交易，不授权下单、撤单、定投、提醒、自选股或社区写入。

## 组合中的职责

```text
AI Berkshire
  研究框架、双源验证、估值纪律、报告审计
        │
        ├── Longbridge MCP
        │     结构化行情、公司、财报、估值和新闻数据
        ├── TradingAgents-astock MCP
        │     A 股多角色辩论、风险观点和阶段性信号
        └── Vibe-Trading MCP
              历史行情、市场数据、因子分析和回测
```

每个聚合 MCP 内的多个工具合计仍然只算一个第三方来源；不同 MCP 若共享底层供应商，也不能互相构成双源。重要财务结论应使用公司 IR、SEC、HKEX、交易所公告或另一家独立数据库交叉验证。

## 推荐安装方式

### 1. 前置检查

需要 Git、Python 3.11 或更高版本，以及 Codex CLI：

```bash
git --version
python3 --version
codex --version
```

Codex 的最新安装方式以 OpenAI 官方文档为准。本仓库的快速入口也列在 [`README.md`](../README.md#1-安装-ai-客户端)。

### 2. 安装 AI Berkshire

推荐使用 `~/ai-berkshire`，保持工具路径与仓库工作流一致：

```bash
git clone https://github.com/xbtlin/ai-berkshire.git ~/ai-berkshire
cd ~/ai-berkshire
bash scripts/install-codex-skills.sh
bash scripts/install-codex-prompts.sh
```

验证生成物和安装结果：

```bash
python3 scripts/sync-codex-skills.py --check
python3 scripts/sync-codex-prompts.py --check
test -f ~/.codex/skills/research/SKILL.md
test -f ~/.codex/skills/longbridge-data/SKILL.md
test -f ~/.codex/prompts/research.md
```

Windows 用户应让安装代理将 shell 命令改写为 PowerShell 等价操作，并保留相同的目标目录结构。

### 3. 安装 Vibe-Trading MCP

建议安装到独立虚拟环境，避免污染系统 Python：

```bash
python3 -m venv ~/.local/share/vibe-trading/venv
~/.local/share/vibe-trading/venv/bin/python -m pip install --upgrade pip
~/.local/share/vibe-trading/venv/bin/python -m pip install --upgrade 'vibe-trading-ai==0.1.12'
~/.local/share/vibe-trading/venv/bin/vibe-trading --version
```

使用绝对路径注册 stdio MCP：

```bash
codex mcp add vibe-trading -- ~/.local/share/vibe-trading/venv/bin/vibe-trading-mcp
codex mcp get vibe-trading
```

在 `~/.codex/config.toml` 的 `[mcp_servers.vibe-trading]` 下设置 `enabled_tools`，只开放 `search_symbol`、`get_market_data`、财务/新闻/资金流等只读研究工具。默认不要加入 `write_file`、`run_swarm`、`backtest`、`factor_analysis`、研究目标写入、交易连接器、账户、journal 或 shadow-account 工具。

核心行情和研究工具无需额外 LLM API Key。本集成由 AI Berkshire 负责编排，不调用 Vibe-Trading 的 `run_swarm`，因此不需要为 Vibe 配置模型 Provider。不要启用 Shell tools，也不要配置真实券商连接器。Vibe 的 `backtest` 会执行本地策略代码；只有审查代码、隔离目录并获得本次明确授权后，才临时加入 allowlist。

### 4. 安装 TradingAgents-astock MCP

本仓库提供异步适配器。MCP 服务与 TradingAgents worker 必须使用两个环境，因为上游 `mootdx` 与当前 MCP 需要不兼容的 `httpx` 版本：

```bash
cd ~/ai-berkshire/services/tradingagents_astock_mcp
uv sync --extra dev
uv run pytest

uv venv ~/.local/share/tradingagents-astock/venv --python 3.12
uv pip install \
  --python ~/.local/share/tradingagents-astock/venv/bin/python \
  'git+https://github.com/simonlin1212/TradingAgents-astock.git@531176ac3161ca13db263495c18b8e0f09fc0eb2'
```

适配器环境不安装 TradingAgents，worker 环境不安装 MCP。固定 commit 对应上游 v0.2.21；默认 worker 路径是 `~/.local/share/tradingagents-astock/venv/bin/python`，自定义路径时通过服务端环境变量 `TRADINGAGENTS_WORKER_PYTHON` 指定。

按照 [`tradingagents-astock-mcp.md`](tradingagents-astock-mcp.md) 配置本地模型环境变量，然后用 `uv` 和仓库的绝对路径注册：

```bash
codex mcp add tradingagents-astock -- \
  /ABSOLUTE/PATH/TO/uv run \
  --project /ABSOLUTE/PATH/TO/ai-berkshire/services/tradingagents_astock_mcp \
  tradingagents-astock-mcp serve --transport stdio
codex mcp get tradingagents-astock
```

默认 Codex-native 模式直接继承当前 Codex 对话模型，不需要模型凭证。只有用户明确要求原版 upstream graph 时，模型凭证才允许通过服务进程环境注入；MCP 工具不接受 API Key、任意 endpoint、路径或命令。

### 5. 配置 Longbridge MCP

全球默认端点：

```bash
codex mcp add longbridge --url https://mcp.longbridge.com
codex mcp login longbridge
codex mcp get longbridge
codex mcp list
```

OAuth 必须由用户在新电脑的浏览器中重新授权。不要复制旧电脑的 OAuth token。中国大陆端点、Agent Auth、Codex Desktop、Claude Code 和常见故障处理见 [`longbridge-mcp.md`](longbridge-mcp.md)。

完成后重启 Codex 或新建任务，使 skills 与 MCP 工具清单重新加载。

## 交给新电脑 AI 的提示词

将下面整段复制给新电脑上的 Codex 或其他具备终端能力的 AI：

```text
请在这台新电脑上复刻我的只读投资研究环境：OpenAI Codex、
https://github.com/xbtlin/ai-berkshire、
https://github.com/simonlin1212/TradingAgents-astock、
https://github.com/HKUDS/Vibe-Trading 和 Longbridge MCP。

请先检测操作系统、CPU 架构、Git、Python 3.11+、Codex CLI、PATH、
~/.codex/config.toml 和现有同名 MCP。缺少组件时使用官方安装方式补齐。
除 OAuth、凭证输入和不可逆操作外，自主执行到验证完成。

要求：
1. 将 AI Berkshire 安装到 ~/ai-berkshire；若目录已存在，先检查 git status
   和 remote，不得删除或覆盖本地改动。运行 install-codex-skills.sh 和
   install-codex-prompts.sh，再执行两个 sync 脚本的 --check。
2. 将 vibe-trading-ai==0.1.12 安装到独立 Python 虚拟环境，用 vibe-trading-mcp
   的绝对路径注册名为 vibe-trading 的 Codex stdio MCP。
3. 为 TradingAgents 创建两个隔离环境：services/tradingagents_astock_mcp 的 uv
   环境只安装和测试 MCP 适配器；~/.local/share/tradingagents-astock/venv 只安装
   commit 531176ac3161ca13db263495c18b8e0f09fc0eb2（v0.2.21）的上游 worker。
   不得把两者合并。注册 tradingagents-astock stdio MCP；默认验证 codex_native=ready，
   不要要求或复制模型凭证。upstream graph 未配置时允许显示 not_ready。
4. 用 https://mcp.longbridge.com 注册名为 longbridge 的远程 MCP，暂停让我
   在浏览器完成 OAuth，再继续验证。
5. 默认仅研究、数据获取、估值和回测。不要配置真实交易，不启用 shell-capable
   MCP tools，不调用下单、撤单、DCA、提醒、自选股或社区写工具。
6. 不复制旧电脑 token，不把 OAuth、API Key、券商凭证写入 Git或终端报告。
7. Windows 上自动改写为 PowerShell 和对应虚拟环境路径。
8. 完成后报告软件版本、仓库 commit、已安装 skills、MCP 状态、验证结果、
   需要我手动完成的步骤和后续更新命令。遇到可恢复错误时继续诊断修复。
```

## 重启后的验收

在新的 Codex 任务中依次执行：

```text
使用 longbridge-data 获取 AAPL.US 的行情、公司和估值数据底稿，仅只读。

使用 Vibe-Trading 获取 AAPL.US 最近 30 个交易日行情，不执行交易。

使用 tradingagents-astock 对 600519.SH 启动 Codex-native 标准研究；
使用当前对话模型，验证 health_check 返回 codex_native=ready，不配置任何 secret。

使用 research 研究苹果：Longbridge 提供结构化行情和财务数据，
Vibe-Trading 提供历史行情与回测，公司 IR/SEC 作为独立来源；
使用 financial_rigor.py 精确计算并用 report_audit.py 审计报告。
```

验收标准：

- `research` 与 `longbridge-data` skills 可发现。
- `vibe-trading`、`tradingagents-astock` 与 `longbridge` MCP 均为 enabled。
- Longbridge 调用不再返回 OAuth 或权限错误。
- Vibe-Trading 能返回行情或回测结果。
- TradingAgents-astock 的 Codex-native 计划无需凭证即可执行；原版上游图可保持 not_ready。
- 输出记录工具参数、数据时间、币种、单位、报告期和独立来源状态。
- 没有读取私人账户数据，也没有执行交易或写操作。

## 更新

```bash
cd ~/ai-berkshire
git pull --rebase
bash scripts/install-codex-skills.sh
bash scripts/install-codex-prompts.sh

~/.local/share/vibe-trading/venv/bin/python -m pip install --upgrade 'vibe-trading-ai==0.1.12'
cd ~/ai-berkshire/services/tradingagents_astock_mcp && uv sync --upgrade && uv run pytest
uv pip install \
  --python ~/.local/share/tradingagents-astock/venv/bin/python --upgrade \
  'git+https://github.com/simonlin1212/TradingAgents-astock.git@531176ac3161ca13db263495c18b8e0f09fc0eb2'
codex mcp list
```

更新前如果仓库存在未提交改动，应先审计并保存，不能用强制重置覆盖。

## 不应迁移的内容

以下状态应在新电脑重新生成或重新授权：

- Longbridge、Codex 和其他 Provider 的 OAuth token。
- `~/.vibe-trading/.env` 中的 API Key 或券商凭证。
- `~/.codex` 中与机器相关的绝对路径和临时会话。
- `.playwright-mcp/`、`.vibe-runs/`、`output/` 等本地运行产物。

需要迁移自定义研究成果时，只提交经过敏感信息审计的 reports、skills、工具代码和非机密配置。
