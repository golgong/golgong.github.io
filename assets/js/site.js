(() => {
  "use strict";

  const consentKey = "golgong-analytics-consent";
  const measurementNode = document.querySelector('meta[name="google-analytics-id"]');
  const measurementId = measurementNode ? measurementNode.content.trim() : "";
  const validMeasurementId = /^G-[A-Z0-9]{6,20}$/.test(measurementId);
  let pageViewSent = false;

  function readChoice() {
    try { return localStorage.getItem(consentKey); } catch (_) { return null; }
  }

  function saveChoice(value) {
    try { localStorage.setItem(consentKey, value); } catch (_) { /* keep this visit only */ }
  }

  function updateChoiceText() {
    const node = document.querySelector("[data-analytics-choice]");
    if (!node) return;
    const choice = readChoice();
    node.textContent = choice === "granted"
      ? "현재 설정: 허용"
      : choice === "denied" ? "현재 설정: 거부" : "현재 설정: 선택 전";
  }

  function setAnalyticsDisabled(disabled) {
    window[`ga-disable-${measurementId}`] = disabled;
  }

  function grantAnalytics() {
    if (!validMeasurementId) return;
    setAnalyticsDisabled(false);
    if (typeof window.gtag !== "function") return;
    window.gtag("consent", "update", { analytics_storage: "granted" });
    if (pageViewSent) return;
    pageViewSent = true;
    window.gtag("event", "page_view", {
      page_location: window.location.href,
      page_title: document.title
    });
  }

  function clearAnalyticsCookies() {
    document.cookie.split(";").forEach((item) => {
      const name = item.split("=")[0].trim();
      if (!name.startsWith("_ga")) return;
      document.cookie = `${name}=; Max-Age=0; path=/; SameSite=Lax`;
      document.cookie = `${name}=; Max-Age=0; path=/; domain=.${location.hostname}; SameSite=Lax`;
    });
  }

  function closeConsentPanel() {
    const panel = document.querySelector(".consent-panel");
    if (panel) panel.remove();
  }

  function chooseAnalytics(value) {
    saveChoice(value);
    if (value === "granted") {
      grantAnalytics();
    } else {
      setAnalyticsDisabled(true);
      if (typeof window.gtag === "function") {
        window.gtag("consent", "update", { analytics_storage: "denied" });
      }
      clearAnalyticsCookies();
    }
    updateChoiceText();
    closeConsentPanel();
  }

  function showConsentPanel(shouldFocus = false) {
    if (!validMeasurementId) return;
    closeConsentPanel();
    const panel = document.createElement("section");
    panel.className = "consent-panel";
    panel.setAttribute("aria-label", "방문 분석 설정");

    const message = document.createElement("p");
    message.textContent = "이 사이트는 Google Analytics를 사용합니다. 허용하기 전에는 방문 분석 이벤트를 보내거나 분석 쿠키를 저장하지 않습니다.";
    panel.appendChild(message);

    const actions = document.createElement("div");
    actions.className = "consent-actions";
    const allow = document.createElement("button");
    allow.type = "button";
    allow.textContent = "허용";
    allow.addEventListener("click", () => chooseAnalytics("granted"));
    const deny = document.createElement("button");
    deny.type = "button";
    deny.textContent = "거부";
    deny.addEventListener("click", () => chooseAnalytics("denied"));
    const policy = document.createElement("a");
    policy.href = "/privacy/";
    policy.textContent = "자세히 보기";
    actions.append(allow, deny, policy);
    panel.appendChild(actions);
    document.body.appendChild(panel);
    if (shouldFocus) allow.focus();
  }

  function initAnalytics() {
    document.querySelectorAll("[data-analytics-settings]").forEach((button) => {
      button.addEventListener("click", () => showConsentPanel(true));
    });
    updateChoiceText();
    const choice = readChoice();
    if (choice === "granted") grantAnalytics();
    if (choice !== "granted" && choice !== "denied") showConsentPanel(false);
  }

  function requireCount(value) {
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  }

  function formatDate(value, suffix = true) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
    if (!match) return "";
    return `${Number(match[2])}월 ${Number(match[3])}일${suffix ? " 기준" : ""}`;
  }

  function formatUpdatedAt(value) {
    const parsed = new Date(value || "");
    if (Number.isNaN(parsed.getTime())) return "";
    return new Intl.DateTimeFormat("ko-KR", {
      month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"
    }).format(parsed) + " 갱신";
  }

  async function fetchJson(url, timeoutMs = 8000, cacheMode = "no-store") {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {
        cache: cacheMode,
        credentials: "omit",
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`visitor stats HTTP ${response.status}`);
      return await response.json();
    } finally {
      window.clearTimeout(timer);
    }
  }

  function normalizeDaily(source) {
    if (!Array.isArray(source) || source.length < 7 || source.length > 30) {
      throw new Error("invalid daily visitor stats");
    }
    const daily = source.map((item) => ({
      date: typeof item.date === "string" && formatDate(item.date) ? item.date : null,
      visitors: requireCount(item.visitors),
      sessions: item.sessions === undefined ? null : requireCount(item.sessions),
      pageViews: item.pageViews === undefined ? null : requireCount(item.pageViews)
    }));
    if (daily.some((item) => item.date === null || item.visitors === null)) {
      throw new Error("invalid daily visitor count");
    }
    return daily;
  }

  function normalizeTotals(value) {
    if (!value) return null;
    const visitors = requireCount(value.visitors);
    const sessions = requireCount(value.sessions);
    const pageViews = requireCount(value.pageViews);
    if (visitors === null || sessions === null || pageViews === null) {
      throw new Error("invalid visitor totals");
    }
    return { visitors, sessions, pageViews };
  }

  function normalizeVisitorStats(stats, source) {
    if (!stats || stats.status !== "ok") throw new Error("visitor stats unavailable");
    if (stats.version === 3) {
      const current = requireCount(stats.current30Minutes && stats.current30Minutes.visitors);
      if (stats.scope !== "analytics-consented" || current === null) {
        throw new Error("invalid live visitor stats");
      }
      const topPages = Array.isArray(stats.topPages) ? stats.topPages.map((item) => {
        const visitors = requireCount(item.visitors);
        const pageViews = requireCount(item.pageViews);
        if (typeof item.path !== "string" || !item.path.startsWith("/") ||
            typeof item.title !== "string" || visitors === null || pageViews === null) {
          throw new Error("invalid page statistics");
        }
        return { path: item.path, title: item.title, visitors, pageViews };
      }) : [];
      return {
        source,
        stale: stats.stale === true,
        dataThrough: stats.dataThrough,
        generatedAt: stats.generatedAt,
        current,
        today: normalizeTotals(stats.today),
        yesterday: normalizeTotals(stats.yesterday),
        last7: normalizeTotals(stats.last7Days),
        last30: normalizeTotals(stats.last30Days),
        daily: normalizeDaily(stats.dailyVisitors),
        topPages
      };
    }
    if (stats.version === 2) {
      return {
        source: "snapshot",
        stale: true,
        dataThrough: stats.throughDate,
        generatedAt: stats.updatedAt,
        current: null,
        today: null,
        yesterday: normalizeTotals(stats.yesterday),
        last7: null,
        last30: null,
        daily: normalizeDaily(stats.dailyVisitors),
        topPages: []
      };
    }
    throw new Error("unsupported visitor stats version");
  }

  async function loadVisitorStats() {
    let endpoint = "";
    try {
      const config = await fetchJson("/data/visitor-api.json", 3000, "default");
      endpoint = typeof config.endpoint === "string" ? config.endpoint.trim() : "";
      if (endpoint && new URL(endpoint).protocol !== "https:") endpoint = "";
    } catch (_) { endpoint = ""; }
    if (endpoint) {
      try {
        return normalizeVisitorStats(await fetchJson(endpoint), "live");
      } catch (_) { /* use the last static snapshot below */ }
    }
    return normalizeVisitorStats(await fetchJson("/data/visitor-stats.json"), "snapshot");
  }

  function drawDailyBars(node, values) {
    node.replaceChildren();
    const maximum = Math.max(...values.map((item) => item.visitors), 1);
    values.forEach((item) => {
      const bar = document.createElement("span");
      bar.style.height = `${Math.max(3, Math.round(item.visitors / maximum * 22))}px`;
      bar.style.opacity = item.visitors === 0 ? ".24" : ".72";
      bar.title = `${formatDate(item.date, false)} ${item.visitors}명`;
      node.appendChild(bar);
    });
    node.hidden = false;
    node.setAttribute("role", "img");
    node.setAttribute("aria-label", `최근 7일 분석 허용 방문자 ${values.map((item) => `${formatDate(item.date, false)} ${item.visitors}명`).join(", ")}`);
  }

  function renderHeaderStats(stats) {
    const root = document.querySelector("[data-visitor-stats]");
    if (!root) return;
    const summary = root.querySelector("[data-visitor-summary]");
    const trend = root.querySelector("[data-visitor-trend]");
    const changeNode = root.querySelector("[data-visitor-change]");
    const bars = root.querySelector("[data-visitor-bars]");
    const dateNode = root.querySelector("[data-visitor-date]");
    const number = new Intl.NumberFormat("ko-KR");
    const totals = stats.today || stats.yesterday;
    const period = stats.today ? "오늘" : "어제";
    summary.textContent = `${period} 방문자 ${number.format(totals.visitors)}명 · 방문 ${number.format(totals.sessions)}회 · 페이지 조회 ${number.format(totals.pageViews)}회`;
    dateNode.textContent = stats.source === "live" ? formatUpdatedAt(stats.generatedAt) : formatDate(stats.dataThrough);
    changeNode.textContent = stats.current === null ? "최근 7일" : `현재 30분 ${number.format(stats.current)}명`;
    drawDailyBars(bars, stats.daily.slice(-7));
    trend.hidden = false;
  }

  function setCount(selector, value) {
    const node = document.querySelector(selector);
    if (node) node.textContent = value === null ? "—" : new Intl.NumberFormat("ko-KR").format(value);
  }

  function renderDashboardChart(node, daily) {
    node.replaceChildren();
    node.style.gridTemplateColumns = `repeat(${daily.length}, minmax(5px, 1fr))`;
    const maximum = Math.max(...daily.map((item) => item.visitors), 1);
    daily.forEach((item) => {
      const bar = document.createElement("span");
      bar.className = "stats-chart__bar";
      bar.style.height = `${Math.max(3, Math.round(item.visitors / maximum * 220))}px`;
      bar.style.opacity = item.visitors === 0 ? ".2" : ".78";
      bar.title = `${formatDate(item.date, false)} 방문자 ${item.visitors}명`;
      node.appendChild(bar);
    });
    node.setAttribute("aria-label", `분석 허용 방문자 일별 추이. ${daily.map((item) => `${formatDate(item.date, false)} ${item.visitors}명`).join(", ")}`);
  }

  function renderDashboardPages(node, pages) {
    node.replaceChildren();
    if (!pages.length) {
      const empty = document.createElement("li");
      empty.textContent = "실시간 집계가 연결되면 표시됩니다.";
      node.appendChild(empty);
      return;
    }
    const number = new Intl.NumberFormat("ko-KR");
    pages.forEach((page) => {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = page.path;
      link.textContent = page.title;
      const count = document.createElement("span");
      count.textContent = `조회 ${number.format(page.pageViews)}회 · 방문자 ${number.format(page.visitors)}명`;
      item.append(link, count);
      node.appendChild(item);
    });
  }

  function renderStatsDashboard(stats) {
    const root = document.querySelector("[data-visitor-dashboard]");
    if (!root) return;
    setCount("[data-stat-current]", stats.current);
    setCount("[data-stat-today-visitors]", stats.today ? stats.today.visitors : null);
    setCount("[data-stat-today-sessions]", stats.today ? stats.today.sessions : null);
    setCount("[data-stat-today-pageviews]", stats.today ? stats.today.pageViews : null);
    setCount("[data-stat-last30-visitors]", stats.last30 ? stats.last30.visitors : null);
    const status = root.querySelector("[data-stats-status]");
    status.textContent = stats.source === "live"
      ? (stats.stale ? "최신 집계가 지연되어 마지막 정상 수치를 표시합니다." : "최신 집계를 표시하고 있습니다.")
      : "실시간 집계에 연결하지 못해 마지막 저장 수치를 표시합니다.";
    const updated = root.querySelector("[data-stats-updated]");
    updated.textContent = formatUpdatedAt(stats.generatedAt) || formatDate(stats.dataThrough);
    const range = root.querySelector("[data-stats-range]");
    range.textContent = `최근 ${stats.daily.length}일 추이`;
    renderDashboardChart(root.querySelector("[data-stats-daily]"), stats.daily);
    renderDashboardPages(root.querySelector("[data-stats-pages]"), stats.topPages);
  }

  async function refreshVisitorStats() {
    try {
      const stats = await loadVisitorStats();
      renderHeaderStats(stats);
      renderStatsDashboard(stats);
    } catch (_) {
      const header = document.querySelector("[data-visitor-summary]");
      if (header) header.textContent = "방문 통계를 확인해 보세요.";
      const status = document.querySelector("[data-stats-status]");
      if (status) status.textContent = "통계를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.";
    }
  }

  function initVisitorStats() {
    if (!document.querySelector("[data-visitor-stats], [data-visitor-dashboard]")) return;
    refreshVisitorStats();
    window.setInterval(() => {
      if (document.visibilityState === "visible") refreshVisitorStats();
    }, 10 * 60 * 1000);
  }

  initAnalytics();
  initVisitorStats();
})();
