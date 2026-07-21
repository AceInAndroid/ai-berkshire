(() => {
  "use strict";

  const POLL_SECONDS = 60;
  const MODULE_ORDER = ["cash", "fixed_income", "gold", "dividend", "broad_market", "technology"];
  const MODULE_LABELS = {
    cash: "现金",
    fixed_income: "固收",
    gold: "黄金",
    dividend: "红利",
    broad_market: "宽基",
    technology: "科技 Beta",
    portfolio: "组合",
  };
  const STATUS_LABELS = {
    eligible: "允许新增",
    watch: "继续观察",
    blocked: "停止新增",
    reduce: "建议减仓",
  };
  const REGIMES = {
    STABILIZING: {
      title: "权重稳定",
      description: "权重指数已止跌，但市场广度尚未恢复；小盘与科技仍处于去杠杆阶段。",
      chip: "稳定中",
      className: "stabilizing",
    },
    DELEVERAGING: {
      title: "去杠杆",
      description: "跌停扩散、中位数显著为负或小盘持续跑输，优先保留现金并降低高 Beta 暴露。",
      chip: "去杠杆",
      className: "deleveraging",
    },
    RECOVERING: {
      title: "风险修复",
      description: "市场广度开始恢复，风险偏好条件连续满足，但仍需等待量价与资金流进一步确认。",
      chip: "修复中",
      className: "recovering",
    },
    RISK_ON: {
      title: "风险偏好回归",
      description: "广度、量价、资金流与科技相对强弱共同确认，可在阶段授权与硬上限内逐步增加风险资产。",
      chip: "RISK ON",
      className: "risk-on",
    },
    RISK_OFF: {
      title: "风险关闭",
      description: "市场修复后再次放量破位，暂停风险资产新增，并按回撤阶梯执行防守。",
      chip: "RISK OFF",
      className: "risk-off",
    },
  };

  const state = {
    dashboard: null,
    countdown: POLL_SECONDS,
    timer: null,
    retryTimer: null,
    loading: false,
  };

  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const asNumber = (value, fallback = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  const formatNumber = (value, digits = 2) => {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "--";
    return new Intl.NumberFormat("zh-CN", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(Number(value));
  };

  const formatCompact = (value) => {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "--";
    const amount = Number(value);
    const abs = Math.abs(amount);
    if (abs >= 1e8) return `${formatNumber(amount / 1e8, 2)}亿`;
    if (abs >= 1e4) return `${formatNumber(amount / 1e4, 1)}万`;
    return formatNumber(amount, 0);
  };

  const formatCny = (value, compact = false) => {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "--";
    return compact ? `¥${formatCompact(value)}` : `¥${formatNumber(value, 0)}`;
  };

  const formatPct = (value, digits = 2, signed = false) => {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "--";
    const numeric = Number(value) * 100;
    const prefix = signed && numeric > 0 ? "+" : "";
    return `${prefix}${formatNumber(numeric, digits)}%`;
  };

  const formatQuotePct = (value) => {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "--";
    const numeric = Number(value);
    return `${numeric > 0 ? "+" : ""}${formatNumber(numeric, 2)}%`;
  };

  const formatTime = (value) => {
    if (!value) return "时间未知";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Shanghai",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(date);
  };

  const toneForNumber = (value) => {
    const numeric = asNumber(value);
    if (numeric > 0) return "positive";
    if (numeric < 0) return "negative";
    return "neutral-text";
  };

  const listHtml = (items, emptyText) => {
    const values = Array.isArray(items) ? items.filter(Boolean) : [];
    if (!values.length) return `<li class="neutral-text">${escapeHtml(emptyText)}</li>`;
    return values.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  };

  const recommendationTitle = (item) => {
    const symbol = item.symbol || MODULE_LABELS[item.module] || item.module || "组合";
    const rule = String(item.rule_id || "规则触发").replaceAll("_", " ");
    return `${symbol} · ${rule}`;
  };

  function setView(mode, message = "") {
    $("loading-state").classList.toggle("hidden", mode !== "loading");
    $("error-state").classList.toggle("hidden", mode !== "error");
    $("dashboard-content").classList.toggle("hidden", mode !== "content");
    if (mode === "error") $("error-message").textContent = message || "请稍后重试。";
  }

  function setScanning(scanning) {
    state.loading = scanning;
    const button = $("refresh-button");
    button.disabled = scanning;
    button.classList.toggle("scanning", scanning);
    button.querySelector("span:nth-child(2)").textContent = scanning ? "扫描中" : "立即扫描";
  }

  function toast(message, error = false) {
    const node = $("toast");
    node.textContent = message;
    node.classList.toggle("error", error);
    node.classList.add("show");
    window.setTimeout(() => node.classList.remove("show"), 3600);
  }

  function resetCountdown() {
    state.countdown = POLL_SECONDS;
    $("countdown").textContent = `${state.countdown}s`;
  }

  function startCountdown() {
    window.clearInterval(state.timer);
    resetCountdown();
    state.timer = window.setInterval(() => {
      state.countdown -= 1;
      if (state.countdown <= 0) {
        state.countdown = POLL_SECONDS;
        loadDashboard({ silent: true });
      }
      $("countdown").textContent = `${state.countdown}s`;
    }, 1000);
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, {
      headers: { Accept: "application/json", ...(options.headers || {}) },
      cache: "no-store",
      ...options,
    });
    let payload = {};
    try {
      payload = await response.json();
    } catch (_error) {
      payload = { message: `服务返回了无法解析的响应（HTTP ${response.status}）` };
    }
    return { response, payload };
  }

  async function loadDashboard({ silent = false } = {}) {
    if (state.loading) return;
    if (!silent && !state.dashboard) setView("loading");
    try {
      const { response, payload } = await requestJson("/api/dashboard");
      if (response.status === 202) {
        $("market-status").textContent = "正在初始化";
        $("market-status").className = "status-chip watch";
        window.clearTimeout(state.retryTimer);
        state.retryTimer = window.setTimeout(() => loadDashboard({ silent }), (payload.retry_after_seconds || 2) * 1000);
        return;
      }
      if (!response.ok) throw new Error(payload.message || `读取失败（HTTP ${response.status}）`);
      state.dashboard = payload;
      renderDashboard(payload);
      setView("content");
      resetCountdown();
    } catch (error) {
      if (state.dashboard && silent) {
        toast(`缓存读取失败：${error.message}`, true);
      } else {
        setView("error", error.message);
      }
    }
  }

  async function refreshDashboard() {
    if (state.loading) return;
    setScanning(true);
    try {
      const { response, payload } = await requestJson("/api/dashboard/refresh", { method: "POST" });
      if (response.status === 202) {
        if (payload.dashboard) {
          state.dashboard = payload.dashboard;
          renderDashboard(payload.dashboard);
          setView("content");
        }
        toast("已有扫描正在进行，正在等待最新结果。");
        window.setTimeout(() => loadDashboard({ silent: true }), (payload.retry_after_seconds || 2) * 1000);
        return;
      }
      if (!response.ok) throw new Error(payload.message || `扫描失败（HTTP ${response.status}）`);
      const dashboard = payload.dashboard || payload;
      state.dashboard = dashboard;
      renderDashboard(dashboard);
      setView("content");
      toast("真实行情扫描完成，快照已写入本地数据库。");
      resetCountdown();
    } catch (error) {
      toast(error.message || "扫描失败，请稍后重试。", true);
      if (!state.dashboard) setView("error", error.message);
    } finally {
      setScanning(false);
    }
  }

  function renderDashboard(data) {
    const regimeCode = data.market_regime?.regime || "STABILIZING";
    const regimeMeta = REGIMES[regimeCode] || {
      title: regimeCode || "未知状态",
      description: "市场状态数据尚不完整，请以风险规则和数据健康状态为准。",
      chip: regimeCode || "未知",
      className: "neutral",
    };
    const stale = (data.data_health?.stale_or_conflicting_symbols || []).length > 0;
    const healthStatus = data.data_health?.status || "unknown";

    $("market-status").textContent = stale ? "数据需复核" : regimeMeta.chip;
    $("market-status").className = `status-chip ${stale ? "degraded" : regimeMeta.className}`;
    $("last-updated").textContent = `${formatTime(data.data_as_of)} · ${healthStatus.toUpperCase()}`;
    $("config-version").textContent = `CONFIG ${data.config_version || "--"}`;

    renderRegime(data, regimeMeta);
    renderMetrics(data);
    renderChart(data);
    renderAllocation(data);
    renderMarket(data);
    renderBeta(data);
    renderSignals(data);
    renderInstruments(data);
    renderExternal(data);
    renderHealth(data);
  }

  function renderRegime(data, meta) {
    const regime = data.market_regime || {};
    const auth = data.initial_authorization?.risk_assets || {};
    const deleveragingText = regime.deleveraging_continues ? " · 去杠杆未结束" : "";
    const title = regime.regime === "STABILIZING" && regime.deleveraging_continues
      ? "权重稳定 / 科技去杠杆"
      : meta.title;
    const node = $("regime-hero");
    node.dataset.code = regime.regime || "MARKET";
    node.innerHTML = `
      <span class="regime-kicker">MARKET REGIME / ${escapeHtml(data.config_version || "--")}</span>
      <span class="regime-score">${asNumber(regime.score)}/8${escapeHtml(deleveragingText)}</span>
      <div class="regime-title">${escapeHtml(title)}</div>
      <p class="regime-desc">${escapeHtml(meta.description)} 首批风险资产授权 ${formatCny(auth.minimum_cny, true)}–${formatCny(auth.maximum_cny, true)}，所有动作仍受阶段额度与组合硬上限约束。</p>
    `;
  }

  function drawdownTone(drawdown) {
    const value = Math.abs(asNumber(drawdown));
    if (value >= 0.16) return "negative";
    if (value >= 0.08) return "warning";
    if (value >= 0.05) return "warning";
    return value > 0 ? "negative" : "neutral-text";
  }

  function renderMetrics(data) {
    const p = data.portfolio || {};
    const metrics = [
      ["总资产", formatCny(p.total_assets), `现金 ${formatCny(p.cash, true)}`, "NAV"],
      ["现金等待区", formatCny(p.cash), `${formatPct(asNumber(p.cash) / Math.max(asNumber(p.total_assets), 1), 1)} 仓位`, "CASH"],
      ["总收益", formatPct(p.total_return, 2, true), `未实现 ${formatCny(p.unrealized_pnl, true)}`, "RETURN", toneForNumber(p.total_return)],
      ["当前回撤", formatPct(-Math.abs(asNumber(p.drawdown)), 2), "5%—20%阶梯风控", "DD", drawdownTone(p.drawdown)],
      ["权益仓位", formatPct(p.equity_weight, 1), `硬上限 ${formatPct(data.policy?.equity_weight_cap, 0)}`, "EQUITY"],
      ["科技仓位", formatPct(p.technology_weight, 1), `目标/上限 ${formatPct(data.policy?.technology_weight_cap, 0)}`, "BETA"],
    ];
    $("metric-rail").innerHTML = metrics.map(([label, value, sub, code, tone = ""]) => `
      <article class="metric">
        <div class="metric-label"><span>${escapeHtml(label)}</span><span>${escapeHtml(code)}</span></div>
        <div class="metric-value ${tone}">${escapeHtml(value)}</div>
        <div class="metric-sub">${escapeHtml(sub)}</div>
      </article>
    `).join("");
  }

  function linePath(points) {
    return points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
  }

  function renderChart(data) {
    const raw = Array.isArray(data.portfolio_history) ? data.portfolio_history : [];
    if (!raw.length) {
      $("performance-chart").innerHTML = '<div class="chart-empty">尚无组合快照。点击“立即扫描”建立首个净值点。</div>';
      return;
    }
    const history = raw.length === 1 ? [raw[0], { ...raw[0] }] : raw;
    const initial = asNumber(data.policy?.initial_capital_cny, 1_000_000) || 1_000_000;
    const navValues = history.map((item) => asNumber(item.total_assets, initial) / initial);
    const ddValues = history.map((item) => -Math.abs(asNumber(item.drawdown)));
    const width = 760;
    const height = 225;
    const pad = { left: 46, right: 18, top: 18, bottom: 28 };
    const chartWidth = width - pad.left - pad.right;
    const chartHeight = height - pad.top - pad.bottom;
    const navMin = Math.min(...navValues, 0.98);
    const navMax = Math.max(...navValues, 1.02);
    const navRange = Math.max(navMax - navMin, 0.02);
    const ddMin = Math.min(...ddValues, -0.01);
    const x = (index) => pad.left + (index / Math.max(history.length - 1, 1)) * chartWidth;
    const navY = (value) => pad.top + ((navMax - value) / navRange) * chartHeight;
    const ddY = (value) => pad.top + ((0 - value) / Math.max(0 - ddMin, 0.01)) * chartHeight;
    const navPoints = navValues.map((value, index) => ({ x: x(index), y: navY(value) }));
    const ddPoints = ddValues.map((value, index) => ({ x: x(index), y: ddY(value) }));
    const area = `${linePath(navPoints)} L${navPoints.at(-1).x},${height - pad.bottom} L${navPoints[0].x},${height - pad.bottom} Z`;
    const grid = [0, 0.25, 0.5, 0.75, 1].map((fraction) => {
      const y = pad.top + fraction * chartHeight;
      const value = navMax - fraction * navRange;
      return `<line class="grid" x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}"/><text x="4" y="${y + 3}">${formatNumber(value, 3)}</text>`;
    }).join("");
    const firstDate = formatTime(raw[0].data_as_of).slice(0, 5);
    const lastDate = formatTime(raw.at(-1).data_as_of).slice(0, 5);
    $("history-range").textContent = raw.length === 1 ? "首个快照" : `${raw.length} 个快照`;
    $("performance-chart").innerHTML = `
      <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="组合净值与回撤走势图" preserveAspectRatio="none">
        <defs><linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d6a84b" stop-opacity=".28"/><stop offset="1" stop-color="#d6a84b" stop-opacity="0"/></linearGradient></defs>
        ${grid}
        <path class="area" d="${area}"/>
        <path class="line" d="${linePath(navPoints)}"/>
        <path class="drawdown" d="${linePath(ddPoints)}"/>
        <text x="${pad.left}" y="${height - 7}">${escapeHtml(firstDate)}</text>
        <text x="${width - pad.right}" y="${height - 7}" text-anchor="end">${escapeHtml(lastDate)}</text>
      </svg>
      <div class="chart-legend"><span>组合净值 ${formatNumber(navValues.at(-1), 3)}</span><span>当前回撤 ${formatPct(ddValues.at(-1), 2)}</span></div>
    `;
  }

  function renderAllocation(data) {
    const modules = data.policy?.modules || {};
    const weights = data.portfolio?.module_weights || {};
    $("allocation-list").innerHTML = MODULE_ORDER.map((key) => {
      const policy = modules[key] || {};
      const actual = Math.max(asNumber(weights[key]), 0);
      const target = Math.max(asNumber(policy.target_weight), 0);
      const cap = Math.max(asNumber(policy.hard_cap_weight), target, 0.01);
      const scale = Math.max(cap, actual, target, 0.01);
      const over = actual > cap + 0.0001;
      const drift = actual - target;
      const driftLabel = Math.abs(drift) < 0.005 ? "接近目标" : drift > 0 ? `超配 ${formatPct(drift, 1)}` : `低配 ${formatPct(-drift, 1)}`;
      return `
        <div class="allocation-row">
          <div class="allocation-name"><strong>${escapeHtml(policy.name || MODULE_LABELS[key])}</strong><small>${escapeHtml(driftLabel)}${over ? " · 超硬上限" : ""}</small></div>
          <div class="allocation-track"><div class="allocation-fill ${over ? "over" : ""}" style="width:${Math.min(actual / scale * 100, 100)}%"></div><i class="allocation-target" style="left:${Math.min(target / scale * 100, 100)}%"></i></div>
          <div class="allocation-values ${over ? "negative" : ""}">${formatPct(actual, 1)}<small>目标 ${formatPct(target, 0)}</small></div>
        </div>
      `;
    }).join("");
  }

  function renderMarket(data) {
    const context = data.market_context || {};
    const regime = data.market_regime || {};
    const breadth = [
      ["上涨 / 下跌", `${formatNumber(context.advances, 0)} / ${formatNumber(context.declines, 0)}`, asNumber(context.advances) >= asNumber(context.declines) ? "positive" : "negative"],
      ["市场中位数", formatQuotePct(context.median_return), toneForNumber(context.median_return)],
      ["跌停家数", formatNumber(context.limit_down_count, 0), asNumber(context.limit_down_count) >= 100 ? "negative" : "positive"],
      ["成交额", formatCny(context.turnover_cny, true), "neutral-text"],
      ["沪深300", formatQuotePct(context.csi300_return), toneForNumber(context.csi300_return)],
      ["中证1000", formatQuotePct(context.csi1000_return), toneForNumber(context.csi1000_return)],
      ["半导体中位数", formatQuotePct(context.semiconductor_median_return), toneForNumber(context.semiconductor_median_return)],
      ["半导体广度", formatPct(context.semiconductor_breadth, 0), asNumber(context.semiconductor_breadth) >= 0.5 ? "positive" : "negative"],
    ];
    $("market-breadth").innerHTML = breadth.map(([label, value, tone]) => `<div class="breadth-item"><span>${escapeHtml(label)}</span><strong class="${tone}">${escapeHtml(value)}</strong></div>`).join("");
    $("recovery-score").textContent = `恢复条件 ${asNumber(regime.score)}/8`;
    $("positive-evidence").innerHTML = listHtml(regime.evidence, "尚无足够修复证据");
    $("risk-evidence").innerHTML = listHtml(regime.risk_evidence, "暂无新增风险证据");
  }

  function betaActionText(action, drawdown) {
    if (action === "reduce") return "减少约三分之一";
    if (action === "blocked") return asNumber(drawdown) >= 0.10 ? "风险复核 / 停止新增" : "停止新增";
    if (action === "eligible") return "允许新增";
    return "继续观察";
  }

  function renderBeta(data) {
    const beta = data.beta_risk || {};
    const action = beta.action || "watch";
    $("beta-action").textContent = betaActionText(action, beta.technology_drawdown);
    $("beta-action").className = `status-chip ${action}`;
    const summaries = [
      ["当前阶段", `Stage ${asNumber(beta.current_stage, 0)}`],
      ["科技仓市值", formatCny(beta.technology_value_cny, true)],
      ["当前浮亏", formatPct(-Math.abs(asNumber(beta.technology_drawdown)), 1)],
      ["本阶段可买", formatCny(beta.authorized_remaining_cny, true)],
    ];
    $("beta-summary").innerHTML = summaries.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");

    const current = asNumber(beta.current_stage, 0);
    const next = asNumber(beta.next_stage, 1);
    $("stage-track").innerHTML = (beta.stages || []).map((stage) => {
      const number = asNumber(stage.stage);
      const cls = number <= current ? "complete" : number === next ? "active" : "future";
      return `<div class="stage ${cls}"><small>STAGE ${number}</small><strong>${escapeHtml(stage.name)}</strong><em>${formatCny(stage.cumulative_amount_cny, true)}</em></div>`;
    }).join("") || '<div class="empty-note">阶段配置尚未加载</div>';

    const instruments = data.policy?.instruments || [];
    const indicators = data.indicators || {};
    const techSymbols = ["159995.SZ", "515050.SH", "512480.SH", "159516.SZ"];
    $("beta-instruments").innerHTML = techSymbols.map((symbol) => {
      const policy = instruments.find((item) => item.symbol === symbol) || { symbol, name: symbol, anchors: {} };
      const indicator = indicators[symbol];
      if (!indicator) return `<div class="beta-tile"><div class="beta-tile-head"><strong>${escapeHtml(symbol)}</strong><small>无数据</small></div><div class="beta-price">--</div><div class="beta-support negative">行情缺失，禁止行动</div></div>`;
      const support = policy.anchors?.support;
      const belowSupport = support && asNumber(indicator.price) < asNumber(support);
      return `
        <div class="beta-tile">
          <div class="beta-tile-head"><strong>${escapeHtml(symbol)}</strong><small>${escapeHtml(policy.name)}</small></div>
          <div class="beta-price ${toneForNumber(indicator.change_pct)}">${formatNumber(indicator.price, 3)}</div>
          <div class="beta-support ${belowSupport ? "negative" : ""}">${belowSupport ? "已跌破" : "支撑"} ${formatNumber(support, 3)} · ${escapeHtml(indicator.trend || "--")}</div>
        </div>
      `;
    }).join("");
  }

  function renderSignals(data) {
    const items = Array.isArray(data.recommendations) ? data.recommendations : [];
    const priority = { reduce: 0, blocked: 1, eligible: 2, watch: 3 };
    const severityPriority = { emergency: 0, risk: 1, action: 2, watch: 3, info: 4 };
    const sorted = [...items].sort((a, b) => {
      const statusDelta = (priority[a.status] ?? 9) - (priority[b.status] ?? 9);
      return statusDelta || (severityPriority[a.severity] ?? 9) - (severityPriority[b.severity] ?? 9);
    });
    const groups = ["eligible", "watch", "blocked", "reduce"];
    const actionCount = sorted.filter((item) => item.status === "eligible").length;
    const riskCount = sorted.filter((item) => ["blocked", "reduce"].includes(item.status)).length;
    $("signal-summary").textContent = `${actionCount} 可执行 · ${riskCount} 风险/阻断`;
    $("signal-groups").innerHTML = groups.map((status) => {
      const group = sorted.filter((item) => item.status === status);
      const cards = group.length ? group.map((item) => {
        const details = item.evidence?.length ? `证据：${item.evidence.join("；")}` : `阻断：${(item.blocking_reasons || []).join("；") || "等待规则确认"}`;
        const invalidation = (item.invalidation || []).join("；");
        return `
          <article class="signal-card">
            <div class="signal-card-top"><span class="signal-card-symbol">${escapeHtml(item.symbol || MODULE_LABELS[item.module] || item.module || "组合")}</span><span class="signal-amount">${asNumber(item.max_amount_cny) > 0 ? formatCny(item.max_amount_cny, true) : "—"}</span></div>
            <h3>${escapeHtml(recommendationTitle(item))}</h3>
            <p>${escapeHtml(details)}</p>
            ${invalidation ? `<p>失效：${escapeHtml(invalidation)}</p>` : ""}
          </article>
        `;
      }).join("") : '<div class="signal-empty">当前无此类信号</div>';
      return `<section class="signal-column"><header class="signal-column-header"><strong class="${status === "reduce" || status === "blocked" ? "negative" : status === "eligible" ? "positive" : "warning"}">${escapeHtml(STATUS_LABELS[status])}</strong><span>${group.length}</span></header>${cards}</section>`;
    }).join("");
  }

  function renderInstruments(data) {
    const instruments = data.policy?.instruments || [];
    const indicators = data.indicators || {};
    const rows = instruments.map((policy) => {
      const indicator = indicators[policy.symbol];
      if (!indicator) {
        return `<tr><td><span>${escapeHtml(policy.symbol)}</span><small class="instrument-name">${escapeHtml(policy.name)}</small></td><td><span class="module-tag">${escapeHtml(MODULE_LABELS[policy.module] || policy.module)}</span></td><td colspan="5" class="neutral-text">暂无行情</td><td><span class="quality-tag stale">缺失</span></td></tr>`;
      }
      let quality = indicator.data_quality || "unknown";
      if (indicator.stale) quality = "stale";
      if (asNumber(indicator.cross_source_deviation) > 0.005) quality = "conflict";
      const qualityLabel = { verified: "已校验", single_source: "单一来源", degraded: "降级", stale: "过期", conflict: "冲突" }[quality] || quality;
      return `
        <tr>
          <td><span>${escapeHtml(policy.symbol)}</span><small class="instrument-name">${escapeHtml(policy.name)}</small></td>
          <td><span class="module-tag">${escapeHtml(MODULE_LABELS[policy.module] || policy.module)}</span></td>
          <td>${formatNumber(indicator.price, 3)}</td>
          <td class="${toneForNumber(indicator.change_pct)}">${formatQuotePct(indicator.change_pct)}</td>
          <td>${formatNumber(indicator.ma5, 3)}</td>
          <td>${formatNumber(indicator.ma20, 3)}</td>
          <td><span class="trend-tag ${escapeHtml(indicator.trend || "flat")}">${escapeHtml({ rising: "上行", falling: "下行", flat: "震荡" }[indicator.trend] || indicator.trend || "--")}</span></td>
          <td><span class="quality-tag ${escapeHtml(quality)}">${escapeHtml(qualityLabel)}</span></td>
        </tr>
      `;
    });
    $("instrument-table-body").innerHTML = rows.join("") || '<tr><td colspan="8" class="empty-note">组合政策未配置标的</td></tr>';
  }

  function flattenExternal(external) {
    if (!external || typeof external !== "object") return {};
    if (external.data && typeof external.data === "object") return external.data;
    return external;
  }

  function renderExternal(data) {
    const external = flattenExternal(data.external_indicators);
    const configured = [
      ["^VIX", "VIX"],
      ["^IXIC", "纳斯达克"],
      ["^SOX", "费城半导体"],
      ["GC=F", "COMEX黄金"],
      ["DX-Y.NYB", "美元指数 DXY"],
      ["CNY=X", "USD/CNY"],
    ];
    $("external-grid").innerHTML = configured.map(([symbol, name]) => {
      const item = external[symbol] || {};
      const price = item.price ?? item.last ?? item.close;
      const change = item.change_pct ?? item.changePercent ?? null;
      const stale = Boolean(item.stale || item.delayed);
      return `<div class="external-item"><span>${escapeHtml(name)}</span><strong class="${toneForNumber(change)}">${formatNumber(price, price && Math.abs(price) < 20 ? 3 : 2)}</strong><small class="${stale ? "negative" : ""}">${change === null ? (price === undefined ? "数据暂缺" : "当前值") : formatQuotePct(change)}${stale ? " · 延迟" : ""}</small></div>`;
    }).join("");
  }

  function renderHealth(data) {
    const health = data.data_health || {};
    const providers = Array.isArray(health.providers) ? health.providers : [];
    const alerts = Array.isArray(data.open_alerts) ? data.open_alerts : [];
    const conflicts = health.stale_or_conflicting_symbols || [];
    const providerRows = providers.length
      ? providers.map((provider) => `<div class="health-row"><span>${escapeHtml(provider.provider || "数据源")}</span><strong class="${provider.status === "ok" ? "positive" : "warning"}">${escapeHtml(provider.status || "unknown")}</strong></div>`).join("")
      : '<div class="health-row"><span>数据源</span><strong class="warning">未报告</strong></div>';
    const alertRows = alerts.length
      ? alerts.slice(0, 5).map((alert) => `<div class="alert-row"><strong>${escapeHtml(alert.rule_id || alert.severity || "风险告警")}</strong><p>${escapeHtml(alert.message || (alert.payload?.blocking_reasons || []).join("；") || "请查看规则详情")}</p></div>`).join("")
      : '<div class="empty-note">当前没有未处理告警</div>';
    $("health-content").innerHTML = `
      <div class="health-section">
        <div class="health-row"><span>系统状态</span><strong class="${health.status === "ok" ? "positive" : "warning"}">${escapeHtml(health.status || "unknown")}</strong></div>
        <div class="health-row"><span>指标覆盖</span><strong>${formatNumber(health.indicator_count, 0)} / ${(data.policy?.instruments || []).length}</strong></div>
        <div class="health-row"><span>过期 / 冲突</span><strong class="${conflicts.length ? "negative" : "positive"}">${conflicts.length ? escapeHtml(conflicts.join(", ")) : "无"}</strong></div>
        <div class="health-row"><span>调度器</span><strong>${health.latest_scheduler_run ? escapeHtml(health.latest_scheduler_run.status || "已运行") : "未运行"}</strong></div>
        ${providerRows}
      </div>
      <div class="health-section"><div class="health-row"><span>未处理告警</span><strong class="${alerts.length ? "negative" : "positive"}">${alerts.length}</strong></div>${alertRows}</div>
    `;
  }

  $("refresh-button").addEventListener("click", refreshDashboard);
  $("retry-button").addEventListener("click", () => loadDashboard());
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) loadDashboard({ silent: Boolean(state.dashboard) });
  });

  startCountdown();
  loadDashboard();
})();
