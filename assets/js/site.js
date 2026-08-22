(() => {
  "use strict";

  const consentKey = "golgong-analytics-consent";
  const containerNode = document.querySelector('meta[name="google-tag-manager-id"]');
  const containerId = containerNode ? containerNode.content.trim() : "";
  const validContainerId = /^GTM-[A-Z0-9]{6,20}$/.test(containerId);
  let tagManagerLoaded = false;

  function readChoice() {
    try { return localStorage.getItem(consentKey); } catch (_) { return null; }
  }

  function saveChoice(value) {
    try { localStorage.setItem(consentKey, value); } catch (_) { /* keep this visit only */ }
  }

  function updateChoiceText() {
    const node = document.querySelector("[data-analytics-choice]");
    if (!node) return;
    if (!validContainerId) {
      node.textContent = "방문 분석이 아직 시작되지 않았습니다.";
      return;
    }
    const choice = readChoice();
    node.textContent = choice === "granted"
      ? "현재 설정: 허용"
      : choice === "denied" ? "현재 설정: 거부" : "현재 설정: 선택 전";
  }

  function loadTagManager() {
    if (!validContainerId || tagManagerLoaded) return;
    tagManagerLoaded = true;
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({ "gtm.start": new Date().getTime(), event: "gtm.js" });
    const script = document.createElement("script");
    script.async = true;
    script.id = "google-tag-manager";
    script.src = `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(containerId)}`;
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
      loadTagManager();
      updateChoiceText();
      closeConsentPanel();
      return;
    }
    const mustReload = tagManagerLoaded;
    if (typeof window.gtag === "function") {
      window.gtag("consent", "update", { analytics_storage: "denied" });
    }
    clearAnalyticsCookies();
    updateChoiceText();
    closeConsentPanel();
    if (mustReload) location.reload();
  }

  function showConsentPanel(shouldFocus = false) {
    if (!validContainerId) return;
    closeConsentPanel();
    const panel = document.createElement("section");
    panel.className = "consent-panel";
    panel.setAttribute("aria-label", "방문 분석 설정");

    const message = document.createElement("p");
    message.textContent = "이 사이트는 Google Tag Manager를 통해 Google Analytics를 사용합니다. 허용하기 전에는 분석 정보를 보내지 않습니다.";
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
      if (!validContainerId) button.hidden = true;
      button.addEventListener("click", () => showConsentPanel(true));
    });
    updateChoiceText();
    if (!validContainerId) return;
    const choice = readChoice();
    if (choice === "granted") loadTagManager();
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
