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

  function formatDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
    if (!match) return "";
    return `${Number(match[2])}월 ${Number(match[3])}일 기준`;
  }

  function drawDailyBars(node, values) {
    node.replaceChildren();
    const maximum = Math.max(...values.map((item) => item.visitors), 1);
    values.forEach((item) => {
      const bar = document.createElement("span");
      bar.style.height = `${Math.max(3, Math.round(item.visitors / maximum * 22))}px`;
      bar.style.opacity = item.visitors === 0 ? ".24" : ".72";
      bar.title = `${formatDate(item.date).replace(" 기준", "")} ${item.visitors}명`;
      node.appendChild(bar);
    });
    node.hidden = false;
    node.setAttribute("role", "img");
    node.setAttribute("aria-label", `최근 7일 분석 허용 방문자 ${values.map((item) => `${formatDate(item.date).replace(" 기준", "")} ${item.visitors}명`).join(", ")}`);
  }

  async function initVisitorStats() {
    const root = document.querySelector("[data-visitor-stats]");
    if (!root) return;
    try {
      const response = await fetch("/data/visitor-stats.json", { cache: "no-store" });
      if (!response.ok) throw new Error("visitor stats unavailable");
      const stats = await response.json();
      const summary = root.querySelector("[data-visitor-summary]");
      const trend = root.querySelector("[data-visitor-trend]");
      const changeNode = root.querySelector("[data-visitor-change]");
      const bars = root.querySelector("[data-visitor-bars]");
      const dateNode = root.querySelector("[data-visitor-date]");
      dateNode.textContent = formatDate(stats.throughDate);

      if (stats.status === "collecting") return;
      const visitors = requireCount(stats.yesterday && stats.yesterday.visitors);
      const sessions = requireCount(stats.yesterday && stats.yesterday.sessions);
      const pageViews = requireCount(stats.yesterday && stats.yesterday.pageViews);
      if (stats.status !== "ok" || visitors === null || sessions === null || pageViews === null) throw new Error("invalid visitor stats");
      const number = new Intl.NumberFormat("ko-KR");
      summary.textContent = `어제 방문자 ${number.format(visitors)}명 · 방문 ${number.format(sessions)}회 · 페이지 조회 ${number.format(pageViews)}회`;

      const dailySource = stats.dailyVisitors;
      if (!Array.isArray(dailySource) || dailySource.length !== 7) throw new Error("invalid daily visitor stats");
      const daily = dailySource.map((item) => ({
        date: typeof item.date === "string" && formatDate(item.date) ? item.date : null,
        visitors: requireCount(item.visitors),
      }));
      if (daily.some((item) => item.date === null || item.visitors === null)) throw new Error("invalid daily visitor count");
      changeNode.textContent = "최근 7일";
      drawDailyBars(bars, daily);
      trend.hidden = false;
    } catch (_) {
      root.hidden = true;
    }
  }

  initAnalytics();
  initVisitorStats();
})();
