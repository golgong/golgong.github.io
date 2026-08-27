from __future__ import annotations

import copy
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from flask import Flask, jsonify, make_response, request


ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
ANALYTICS_API = "https://analyticsdata.googleapis.com/v1beta"
PUBLIC_PAGE = re.compile(
    r"^(?:/|/about/?|/privacy/?|/stats/?|/\d{4}/\d{2}/\d{2}/[a-z0-9-]+/?)$"
)
METRICS = ("activeUsers", "sessions", "screenPageViews")
SEOUL_TIME = timezone(timedelta(hours=9), name="Asia/Seoul")


class UpstreamError(RuntimeError):
    pass


def _required_property_id() -> str:
    value = os.environ.get("GA4_PROPERTY_ID", "").strip()
    value = value.removeprefix("properties/")
    if not value.isdigit():
        raise RuntimeError("GA4_PROPERTY_ID must be a numeric GA4 property ID")
    return value


def _count(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise UpstreamError("GA4 returned a non-integer metric") from exc
    if number < 0:
        raise UpstreamError("GA4 returned a negative metric")
    return number


def _metric_values(row: dict[str, Any] | None) -> dict[str, int]:
    values = [] if row is None else row.get("metricValues", [])
    if len(values) != len(METRICS):
        if row is None:
            return {"visitors": 0, "sessions": 0, "pageViews": 0}
        raise UpstreamError("GA4 metric count mismatch")
    return {
        "visitors": _count(values[0].get("value")),
        "sessions": _count(values[1].get("value")),
        "pageViews": _count(values[2].get("value")),
    }


def _single_total(report: dict[str, Any]) -> dict[str, int]:
    rows = report.get("rows", [])
    if len(rows) > 1:
        raise UpstreamError("GA4 aggregate report returned multiple rows")
    return _metric_values(rows[0] if rows else None)


def _daily_rows(report: dict[str, Any], start: date, end: date) -> list[dict[str, Any]]:
    found: dict[str, dict[str, int]] = {}
    for row in report.get("rows", []):
        dimensions = row.get("dimensionValues", [])
        if len(dimensions) != 1:
            raise UpstreamError("GA4 daily report dimension mismatch")
        raw_date = str(dimensions[0].get("value", ""))
        try:
            parsed = datetime.strptime(raw_date, "%Y%m%d").date()
        except ValueError as exc:
            raise UpstreamError("GA4 returned an invalid date") from exc
        if parsed < start or parsed > end:
            raise UpstreamError("GA4 returned a date outside the fixed range")
        key = parsed.isoformat()
        if key in found:
            raise UpstreamError("GA4 returned a duplicate date")
        found[key] = _metric_values(row)

    result = []
    cursor = start
    while cursor <= end:
        key = cursor.isoformat()
        result.append({"date": key, **found.get(key, {"visitors": 0, "sessions": 0, "pageViews": 0})})
        cursor += timedelta(days=1)
    return result


def _top_pages(metrics_report: dict[str, Any], titles_report: dict[str, Any]) -> list[dict[str, Any]]:
    titles: dict[str, tuple[int, str]] = {}
    for row in titles_report.get("rows", []):
        dimensions = row.get("dimensionValues", [])
        values = row.get("metricValues", [])
        if len(dimensions) != 2 or len(values) != 1:
            raise UpstreamError("GA4 page title report shape mismatch")
        path = str(dimensions[0].get("value", "")).strip()
        title = str(dimensions[1].get("value", "")).strip()
        views = _count(values[0].get("value"))
        if PUBLIC_PAGE.fullmatch(path) and title and (path not in titles or views > titles[path][0]):
            titles[path] = (views, title[:160])

    pages = []
    for row in metrics_report.get("rows", []):
        dimensions = row.get("dimensionValues", [])
        values = row.get("metricValues", [])
        if len(dimensions) != 1 or len(values) != 2:
            raise UpstreamError("GA4 page metrics report shape mismatch")
        path = str(dimensions[0].get("value", "")).strip()
        if not PUBLIC_PAGE.fullmatch(path):
            continue
        pages.append({
            "path": path,
            "title": titles.get(path, (0, path))[1],
            "visitors": _count(values[1].get("value")),
            "pageViews": _count(values[0].get("value")),
        })
        if len(pages) == 10:
            break
    return pages


def _create_authorized_session():
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default(scopes=[ANALYTICS_SCOPE])
    return AuthorizedSession(credentials)


@dataclass
class AnalyticsClient:
    property_id: str
    session: Any
    timeout_seconds: float = 8.0

    def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{ANALYTICS_API}/properties/{self.property_id}:{method}"
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout_seconds)
        except Exception as exc:
            raise UpstreamError("GA4 request failed") from exc
        if response.status_code != 200:
            raise UpstreamError(f"GA4 request returned HTTP {response.status_code}")
        try:
            value = response.json()
        except ValueError as exc:
            raise UpstreamError("GA4 returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise UpstreamError("GA4 returned an invalid response")
        return value

    def batch_reports(self, reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
        response = self._post("batchRunReports", {"requests": reports})
        values = response.get("reports")
        if not isinstance(values, list) or len(values) != len(reports):
            raise UpstreamError("GA4 batch response count mismatch")
        return values

    def realtime_visitors(self) -> int:
        response = self._post("runRealtimeReport", {"metrics": [{"name": "activeUsers"}]})
        rows = response.get("rows", [])
        if not rows:
            return 0
        if len(rows) != 1 or len(rows[0].get("metricValues", [])) != 1:
            raise UpstreamError("GA4 realtime response shape mismatch")
        return _count(rows[0]["metricValues"][0].get("value"))


def _total_request(start: date, end: date) -> dict[str, Any]:
    return {
        "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
        "metrics": [{"name": name} for name in METRICS],
        "keepEmptyRows": True,
    }


def collect_stats(client: AnalyticsClient, now: datetime | None = None) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(SEOUL_TIME)
    today = current.date()
    yesterday = today - timedelta(days=1)
    start_7 = today - timedelta(days=6)
    start_30 = today - timedelta(days=29)
    daily_request = {
        **_total_request(start_30, today),
        "dimensions": [{"name": "date"}],
        "orderBys": [{"dimension": {"dimensionName": "date"}}],
    }
    page_metrics_request = {
        "dateRanges": [{"startDate": start_30.isoformat(), "endDate": today.isoformat()}],
        "dimensions": [{"name": "pagePath"}],
        "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}],
        "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
        "limit": 50,
    }
    page_titles_request = {
        "dateRanges": [{"startDate": start_30.isoformat(), "endDate": today.isoformat()}],
        "dimensions": [{"name": "pagePath"}, {"name": "pageTitle"}],
        "metrics": [{"name": "screenPageViews"}],
        "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
        "limit": 100,
    }
    reports = client.batch_reports([
        _total_request(today, today),
        _total_request(yesterday, yesterday),
        _total_request(start_7, today),
        _total_request(start_30, today),
        daily_request,
        page_metrics_request,
        page_titles_request,
    ])
    return {
        "version": 3,
        "status": "ok",
        "scope": "analytics-consented",
        "metric": "activeUsers",
        "generatedAt": current.isoformat(timespec="seconds"),
        "dataThrough": today.isoformat(),
        "stale": False,
        "current30Minutes": {"visitors": client.realtime_visitors()},
        "today": _single_total(reports[0]),
        "yesterday": _single_total(reports[1]),
        "last7Days": _single_total(reports[2]),
        "last30Days": _single_total(reports[3]),
        "dailyVisitors": _daily_rows(reports[4], start_30, today),
        "topPages": _top_pages(reports[5], reports[6]),
    }


class CachedCollector:
    def __init__(self, collect: Callable[[], dict[str, Any]], ttl_seconds: int) -> None:
        self._collect = collect
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._value: dict[str, Any] | None = None
        self._expires_at = 0.0

    def get(self) -> dict[str, Any]:
        if self._value is not None and time.monotonic() < self._expires_at:
            return copy.deepcopy(self._value)
        with self._lock:
            if self._value is not None and time.monotonic() < self._expires_at:
                return copy.deepcopy(self._value)
            try:
                value = self._collect()
            except Exception:
                if self._value is None:
                    raise
                stale = copy.deepcopy(self._value)
                stale["stale"] = True
                self._expires_at = time.monotonic() + min(60, self._ttl_seconds)
                return stale
            self._value = copy.deepcopy(value)
            self._expires_at = time.monotonic() + self._ttl_seconds
            return value


def create_app(collector: CachedCollector | None = None) -> Flask:
    app = Flask(__name__)
    allowed_origin = os.environ.get("ALLOWED_ORIGIN", "https://golgong.github.io").rstrip("/")
    active_collector = collector
    collector_lock = threading.Lock()

    def get_collector() -> CachedCollector:
        nonlocal active_collector
        if active_collector is not None:
            return active_collector
        with collector_lock:
            if active_collector is not None:
                return active_collector
            property_id = _required_property_id()
            client = AnalyticsClient(property_id, _create_authorized_session())
            ttl_seconds = int(os.environ.get("CACHE_TTL_SECONDS", "1800"))
            if ttl_seconds < 60 or ttl_seconds > 3600:
                raise RuntimeError("CACHE_TTL_SECONDS must be between 60 and 3600")
            active_collector = CachedCollector(lambda: collect_stats(client), ttl_seconds)
            return active_collector

    def permitted_origin() -> bool:
        # The response contains only public aggregate data. CORS limits browser
        # embedding; it is deliberately not treated as API authentication.
        origin = request.headers.get("Origin")
        return origin is None or origin.rstrip("/") == allowed_origin

    def apply_headers(response):
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") == allowed_origin:
            response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Vary"] = "Origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.route("/v1/visitor-stats", methods=["GET", "OPTIONS"])
    def visitor_stats():
        if not permitted_origin():
            return apply_headers(make_response(jsonify({"status": "forbidden"}), 403))
        if request.args:
            return apply_headers(make_response(jsonify({"status": "invalid_request"}), 400))
        if request.method == "OPTIONS":
            response = make_response("", 204)
            response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Max-Age"] = "86400"
            return apply_headers(response)
        try:
            payload = get_collector().get()
        except Exception:
            app.logger.exception("visitor statistics collection failed")
            response = make_response(jsonify({"status": "unavailable"}), 503)
            response.headers["Cache-Control"] = "no-store"
            return apply_headers(response)
        response = make_response(jsonify(payload), 200)
        response.headers["Cache-Control"] = "public, max-age=300, stale-if-error=86400"
        return apply_headers(response)

    return app


app = create_app()
