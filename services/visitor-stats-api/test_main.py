from __future__ import annotations

import os
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ.setdefault("GA4_PROPERTY_ID", "123456789")

from main import AnalyticsClient, CachedCollector, UpstreamError, _daily_rows, _top_pages, collect_stats, create_app


def payload() -> dict:
    return {
        "version": 3,
        "status": "ok",
        "scope": "analytics-consented",
        "metric": "activeUsers",
        "generatedAt": "2026-08-28T12:00:00+09:00",
        "dataThrough": "2026-08-28",
        "stale": False,
        "current30Minutes": {"visitors": 1},
        "today": {"visitors": 2, "sessions": 3, "pageViews": 4},
        "yesterday": {"visitors": 1, "sessions": 2, "pageViews": 3},
        "last7Days": {"visitors": 5, "sessions": 8, "pageViews": 13},
        "last30Days": {"visitors": 7, "sessions": 11, "pageViews": 19},
        "dailyVisitors": [],
        "topPages": [],
    }


class CollectorTests(unittest.TestCase):
    def test_cache_and_stale_fallback(self) -> None:
        calls = 0

        def collect():
            nonlocal calls
            calls += 1
            if calls > 1:
                raise UpstreamError("offline")
            return payload()

        collector = CachedCollector(collect, 60)
        first = collector.get()
        self.assertFalse(first["stale"])
        collector._expires_at = 0
        stale = collector.get()
        self.assertTrue(stale["stale"])
        self.assertEqual(calls, 2)
        self.assertGreater(collector._expires_at, time.monotonic())

    def test_concurrent_refresh_runs_once(self) -> None:
        calls = 0

        def collect():
            nonlocal calls
            calls += 1
            time.sleep(0.05)
            return payload()

        collector = CachedCollector(collect, 60)
        threads = [threading.Thread(target=collector.get) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(calls, 1)


class ParserTests(unittest.TestCase):
    def test_batch_reports_split_at_google_limit_and_keep_order(self) -> None:
        class Session:
            def __init__(self):
                self.calls = []

            def post(self, url, json, timeout):
                self.calls.append(json["requests"])
                offset = sum(len(batch) for batch in self.calls[:-1])

                class Response:
                    status_code = 200

                    def json(self_inner):
                        return {"reports": [
                            {"requestIndex": offset + index}
                            for index in range(len(json["requests"]))
                        ]}

                return Response()

        session = Session()
        client = AnalyticsClient("123456789", session)
        reports = [{"requestIndex": index} for index in range(7)]
        result = client.batch_reports(reports)

        self.assertEqual([len(batch) for batch in session.calls], [5, 2])
        self.assertEqual([item["requestIndex"] for item in result], list(range(7)))

    def test_period_totals_are_not_summed_from_daily_users(self) -> None:
        def totals(visitors, sessions=0, views=0):
            return {"rows": [{"metricValues": [
                {"value": str(visitors)}, {"value": str(sessions)}, {"value": str(views)}
            ]}]}

        class Client:
            requests = None

            def batch_reports(self, requests):
                self.requests = requests
                return [
                    totals(1, 1, 1),
                    totals(1, 1, 1),
                    totals(1, 2, 2),
                    totals(1, 2, 2),
                    {"rows": [
                        {"dimensionValues": [{"value": "20260827"}], "metricValues": [{"value": "1"}, {"value": "1"}, {"value": "1"}]},
                        {"dimensionValues": [{"value": "20260828"}], "metricValues": [{"value": "1"}, {"value": "1"}, {"value": "1"}]},
                    ]},
                    {"rows": []},
                    {"rows": []},
                ]

            def realtime_visitors(self):
                return 1

        client = Client()
        result = collect_stats(client, datetime(2026, 8, 28, 12, tzinfo=timezone(timedelta(hours=9))))
        self.assertEqual(result["last7Days"]["visitors"], 1)
        self.assertEqual(sum(day["visitors"] for day in result["dailyVisitors"]), 2)
        self.assertEqual(client.requests[2]["dateRanges"][0], {
            "startDate": "2026-08-22", "endDate": "2026-08-28"
        })

    def test_daily_rows_fill_missing_dates(self) -> None:
        rows = _daily_rows(
            {"rows": [{
                "dimensionValues": [{"value": "20260827"}],
                "metricValues": [{"value": "2"}, {"value": "3"}, {"value": "4"}],
            }]},
            datetime(2026, 8, 26).date(),
            datetime(2026, 8, 28).date(),
        )
        self.assertEqual([item["visitors"] for item in rows], [0, 2, 0])

    def test_daily_rows_reject_negative_metric(self) -> None:
        with self.assertRaises(UpstreamError):
            _daily_rows(
                {"rows": [{
                    "dimensionValues": [{"value": "20260828"}],
                    "metricValues": [{"value": "-1"}, {"value": "0"}, {"value": "0"}],
                }]},
                datetime(2026, 8, 28).date(),
                datetime(2026, 8, 28).date(),
            )

    def test_top_pages_remove_non_public_paths(self) -> None:
        metrics = {"rows": [
            {"dimensionValues": [{"value": "/admin"}], "metricValues": [{"value": "9"}, {"value": "4"}]},
            {"dimensionValues": [{"value": "/2026/08/28/example/"}], "metricValues": [{"value": "5"}, {"value": "3"}]},
        ]}
        titles = {"rows": [
            {"dimensionValues": [{"value": "/2026/08/28/example/"}, {"value": "Old"}], "metricValues": [{"value": "1"}]},
            {"dimensionValues": [{"value": "/2026/08/28/example/"}, {"value": "Current"}], "metricValues": [{"value": "4"}]},
        ]}
        result = _top_pages(metrics, titles)
        self.assertEqual([item["path"] for item in result], ["/2026/08/28/example/"])
        self.assertEqual(result[0]["title"], "Current")
        self.assertEqual(result[0]["pageViews"], 5)


class HttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collector = CachedCollector(payload, 60)
        self.client = create_app(self.collector).test_client()

    def test_health_endpoint(self) -> None:
        response = self.client.get("/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_allowed_origin_and_cache_headers(self) -> None:
        response = self.client.get("/v1/visitor-stats", headers={"Origin": "https://golgong.github.io"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://golgong.github.io")
        self.assertIn("stale-if-error", response.headers["Cache-Control"])
        self.assertEqual(response.headers["Vary"], "Origin")

    def test_disallowed_origin(self) -> None:
        response = self.client.get("/v1/visitor-stats", headers={"Origin": "https://example.com"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        self.assertEqual(response.headers["Vary"], "Origin")

    def test_disallowed_origin_options(self) -> None:
        response = self.client.options("/v1/visitor-stats", headers={"Origin": "https://example.com"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_request_without_origin_is_public_aggregate(self) -> None:
        response = self.client.get("/v1/visitor-stats")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Vary"], "Origin")

    def test_query_parameters_are_rejected(self) -> None:
        response = self.client.get("/v1/visitor-stats?date=all")
        self.assertEqual(response.status_code, 400)

    def test_options(self) -> None:
        response = self.client.options("/v1/visitor-stats", headers={"Origin": "https://golgong.github.io"})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers["Access-Control-Allow-Methods"], "GET, OPTIONS")

    def test_first_failure_is_generic_503(self) -> None:
        collector = CachedCollector(lambda: (_ for _ in ()).throw(UpstreamError("secret")), 60)
        response = create_app(collector).test_client().get("/v1/visitor-stats")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {"status": "unavailable"})


if __name__ == "__main__":
    unittest.main()
