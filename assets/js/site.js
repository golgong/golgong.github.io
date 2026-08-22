(() => {
  "use strict";

  const consentKey = "golgong-analytics-consent";
  const measurementNode = document.querySelector('meta[name="google-analytics-id"]');
  const measurementId = measurementNode ? measurementNode.content.trim() : "";
  const validMeasurementId = /^G-[A-Z0-9]{6,20}$/.test(measurementId);
  let analyticsLoaded = false;

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

  function loadAnalytics() {
    if (!validMeasurementId) return;
    setAnalyticsDisabled(false);
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
    window.gtag("consent", "update", { analytics_storage: "granted" });
    if (analyticsLoaded) return;
    analyticsLoaded = true;
    window.gtag("js", new Date());
    window.gtag("config", measurementId, {
      allow_google_signals: false,
      allow_ad_personalization_signals: false
    });
    const script = document.createElement("script");
    script.async = true;
    script.id = "google-analytics-tag";
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
    document.head.appendChild(script);
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
      loadAnalytics();
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
    message.textContent = "이 사이트는 Google Analytics를 사용합니다. 허용하기 전에는 분석 정보를 보내지 않습니다.";
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
    if (choice === "granted") loadAnalytics();
    if (choice !== "granted" && choice !== "denied") showConsentPanel(false);
  }

  function requireCount(value) {
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  }

  function formatDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
    if (!match) return "";
    return `${Number(match[2])}월 ${Number(match[3])}일까지`;
  }

  function drawWeeklyBars(node, values) {
    node.replaceChildren();
    const visible = values.filter((value) => value !== null);
    if (visible.length < 2) {
      node.hidden = true;
      return;
    }
    const maximum = Math.max(...visible, 1);
    values.forEach((value) => {
      const bar = document.createElement("span");
      bar.style.height = value === null ? "3px" : `${Math.max(3, Math.round(value / maximum * 22))}px`;
      bar.style.opacity = value === null ? ".2" : ".72";
      node.appendChild(bar);
    });
    node.hidden = false;
    node.setAttribute("role", "img");
    node.setAttribute("aria-label", `최근 4주 분석 허용 방문자 ${values.map((value) => value === null ? "5명 미만" : `${value}명`).join(", ")}`);
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
      if (stats.status === "low_volume") {
        summary.textContent = "최근 7일 분석 허용 방문자 5명 미만";
        trend.hidden = true;
        return;
      }
      const visitors = requireCount(stats.current7Days && stats.current7Days.visitors);
      const pageViews = requireCount(stats.current7Days && stats.current7Days.pageViews);
      if (stats.status !== "ok" || visitors === null || pageViews === null) throw new Error("invalid visitor stats");
      const number = new Intl.NumberFormat("ko-KR");
      summary.textContent = `최근 7일 분석 허용 방문자 ${number.format(visitors)}명 · 페이지 조회 ${number.format(pageViews)}회`;

      const change = Number.isSafeInteger(stats.changeVisitors) ? stats.changeVisitors : null;
      if (change === null) {
        changeNode.textContent = "비교할 이전 기간이 없습니다.";
      } else if (change > 0) {
        changeNode.textContent = `지난 7일보다 ${number.format(change)}명 늘었습니다.`;
      } else if (change < 0) {
        changeNode.textContent = `지난 7일보다 ${number.format(Math.abs(change))}명 줄었습니다.`;
      } else {
        changeNode.textContent = "지난 7일과 같습니다.";
      }
      const weeklySource = stats.weeklyVisitors;
      if (!Array.isArray(weeklySource) || weeklySource.length !== 4) throw new Error("invalid weekly visitor stats");
      const weekly = weeklySource.map((value) => value === null ? null : requireCount(value));
      if (weekly.some((value, index) => value === null && weeklySource[index] !== null)) {
        throw new Error("invalid weekly visitor count");
      }
      drawWeeklyBars(bars, weekly);
      trend.hidden = false;
    } catch (_) {
      root.hidden = true;
    }
  }

  initAnalytics();
  initVisitorStats();
})();
