from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import update_visitor_stats as visitor


class VisitorStatsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 22, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))

    def build(self, active_users: list[int], sessions: int = 4, page_views: int = 5) -> dict:
        through_date = self.now.date().replace(day=21)
        dates = visitor.daily_dates(through_date)
        report = {
            report_date: {
                "activeUsers": value,
                "sessions": sessions if index == len(dates) - 1 else 0,
                "screenPageViews": page_views if index == len(dates) - 1 else 0,
            }
            for index, (report_date, value) in enumerate(zip(dates, active_users, strict=True))
        }
        with patch.object(visitor, "request_daily_report", return_value=report):
            return visitor.build_summary(
                access_token="test-token",
                property_id="123456789",
                now=self.now,
            )

    def test_daily_dates_are_consecutive(self) -> None:
        dates = visitor.daily_dates(self.now.date())
        self.assertEqual(len(dates), 7)
        self.assertEqual(dates[-1], self.now.date())
        for previous, current in zip(dates, dates[1:]):
            self.assertEqual(previous.toordinal() + 1, current.toordinal())

    def test_normal_summary(self) -> None:
        summary = visitor.validate_summary(self.build([0, 1, 0, 3, 1, 4, 2]))
        self.assertEqual(summary["throughDate"], "2026-08-21")
        self.assertEqual(summary["yesterday"], {"visitors": 2, "sessions": 4, "pageViews": 5})
        self.assertEqual([item["visitors"] for item in summary["dailyVisitors"]], [0, 1, 0, 3, 1, 4, 2])

    def test_zero_and_low_counts_are_preserved(self) -> None:
        summary = visitor.validate_summary(self.build([0, 0, 0, 0, 0, 1, 0], sessions=0, page_views=0))
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["yesterday"], {"visitors": 0, "sessions": 0, "pageViews": 0})
        self.assertEqual(summary["dailyVisitors"][-2]["visitors"], 1)

    def test_missing_api_days_are_zero_filled(self) -> None:
        through_date = self.now.date().replace(day=21)
        report_date = through_date
        with patch.object(visitor, "request_daily_report", return_value={
            report_date: {"activeUsers": 2, "sessions": 4, "screenPageViews": 5}
        }):
            summary = visitor.build_summary(
                access_token="test-token", property_id="123456789", now=self.now
            )
        self.assertEqual([item["visitors"] for item in summary["dailyVisitors"]], [0, 0, 0, 0, 0, 0, 2])

    def test_latest_daily_mismatch_is_rejected(self) -> None:
        summary = self.build([0, 1, 0, 3, 1, 4, 2])
        summary["dailyVisitors"][-1]["visitors"] = 99
        with self.assertRaisesRegex(RuntimeError, "differs from yesterday"):
            visitor.validate_summary(summary)

    def test_non_consecutive_date_is_rejected(self) -> None:
        summary = self.build([0, 1, 0, 3, 1, 4, 2])
        summary["dailyVisitors"][2]["date"] = "2026-01-01"
        with self.assertRaisesRegex(RuntimeError, "not consecutive"):
            visitor.validate_summary(summary)

    def test_atomic_write_round_trip(self) -> None:
        summary = visitor.validate_summary(self.build([0, 1, 0, 3, 1, 4, 2]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "visitor-stats.json"
            visitor.atomic_write(path, summary)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), summary)


if __name__ == "__main__":
    unittest.main()
