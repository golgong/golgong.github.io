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

    def build(self, active_users: list[int], page_views: int = 33) -> dict:
        calls = iter(active_users)

        def fake_report(**kwargs):
            value = next(calls)
            result = {"activeUsers": value}
            if "screenPageViews" in kwargs["metrics"]:
                result["screenPageViews"] = page_views
            return result

        with patch.object(visitor, "request_report", side_effect=fake_report):
            return visitor.build_summary(
                access_token="test-token",
                property_id="123456789",
                now=self.now,
            )

    def test_weekly_periods_do_not_overlap(self) -> None:
        periods = visitor.weekly_periods(self.now.date())
        self.assertEqual(len(periods), 4)
        for start, end in periods:
            self.assertEqual((end - start).days, 6)
        for previous, current in zip(periods, periods[1:]):
            self.assertEqual(previous[1].toordinal() + 1, current[0].toordinal())

    def test_normal_summary(self) -> None:
        summary = visitor.validate_summary(self.build([7, 9, 12, 15]))
        self.assertEqual(summary["throughDate"], "2026-08-20")
        self.assertEqual(summary["current7Days"], {"visitors": 15, "pageViews": 33})
        self.assertEqual(summary["previous7Days"], {"visitors": 12})
        self.assertEqual(summary["changeVisitors"], 3)
        self.assertEqual(summary["weeklyVisitors"], [7, 9, 12, 15])

    def test_current_low_volume_suppresses_all_counts(self) -> None:
        summary = visitor.validate_summary(self.build([10, 11, 12, 4]))
        self.assertEqual(summary["status"], "low_volume")
        self.assertIsNone(summary["current7Days"])
        self.assertEqual(summary["weeklyVisitors"], [])

    def test_previous_low_volume_suppresses_comparison(self) -> None:
        summary = visitor.validate_summary(self.build([8, 9, 4, 12]))
        self.assertIsNone(summary["previous7Days"])
        self.assertIsNone(summary["changeVisitors"])
        self.assertEqual(summary["weeklyVisitors"], [8, 9, None, 12])

    def test_arithmetic_mismatch_is_rejected(self) -> None:
        summary = self.build([7, 9, 12, 15])
        summary["changeVisitors"] = 99
        with self.assertRaisesRegex(RuntimeError, "arithmetic mismatch"):
            visitor.validate_summary(summary)

    def test_atomic_write_round_trip(self) -> None:
        summary = visitor.validate_summary(self.build([7, 9, 12, 15]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "visitor-stats.json"
            visitor.atomic_write(path, summary)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), summary)


if __name__ == "__main__":
    unittest.main()
