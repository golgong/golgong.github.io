from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "visitor-stats.json"
API_URL = "https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
SEOUL = ZoneInfo("Asia/Seoul")
DAILY_WINDOW_DAYS = 7


def require_property_id(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"\d+", value):
        raise RuntimeError("GA_PROPERTY_ID must contain digits only")
    return value


def request_daily_report(
    *, access_token: str, property_id: str, start_date: date, end_date: date,
) -> dict[date, dict[str, int]]:
    metrics = ("activeUsers", "sessions", "screenPageViews")
    body = json.dumps(
        {
            "dateRanges": [
                {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}
            ],
            "dimensions": [{"name": "date"}],
            "metrics": [{"name": name} for name in metrics],
            "orderBys": [{"dimension": {"dimensionName": "date"}}],
            "keepEmptyRows": True,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        API_URL.format(property_id=property_id),
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "golgong-visitor-stats/2.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Google Analytics Data API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Google Analytics Data API request failed: {exc.reason}") from exc

    dimension_headers = [item.get("name") for item in payload.get("dimensionHeaders", [])]
    metric_headers = [item.get("name") for item in payload.get("metricHeaders", [])]
    if dimension_headers != ["date"]:
        raise RuntimeError(f"unexpected dimension headers: {dimension_headers}")
    if metric_headers != list(metrics):
        raise RuntimeError(f"unexpected metric headers: {metric_headers}")

    result: dict[date, dict[str, int]] = {}
    for row in payload.get("rows", []):
        dimensions = row.get("dimensionValues", [])
        values = row.get("metricValues", [])
        if len(dimensions) != 1 or len(values) != len(metrics):
            raise RuntimeError("daily report value count mismatch")
        raw_date = str(dimensions[0].get("value", ""))
        if not re.fullmatch(r"\d{8}", raw_date):
            raise RuntimeError(f"unexpected date value: {raw_date!r}")
        report_date = datetime.strptime(raw_date, "%Y%m%d").date()
        if not start_date <= report_date <= end_date:
            raise RuntimeError(f"daily report date is outside the requested range: {report_date}")
        if report_date in result:
            raise RuntimeError(f"duplicate daily report date: {report_date}")
        counts: dict[str, int] = {}
        for name, item in zip(metrics, values, strict=True):
            raw = str(item.get("value", ""))
            if not re.fullmatch(r"\d+", raw):
                raise RuntimeError(f"unexpected value for {name}: {raw!r}")
            counts[name] = int(raw)
        result[report_date] = counts
    return result


def daily_dates(through_date: date) -> list[date]:
    return [
        through_date - timedelta(days=offset)
        for offset in range(DAILY_WINDOW_DAYS - 1, -1, -1)
    ]


def build_summary(*, access_token: str, property_id: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(SEOUL)
    if now.tzinfo is None:
        raise RuntimeError("now must be timezone-aware")
    through_date = now.astimezone(SEOUL).date() - timedelta(days=1)
    dates = daily_dates(through_date)
    report = request_daily_report(
        access_token=access_token,
        property_id=property_id,
        start_date=dates[0],
        end_date=dates[-1],
    )
    zero = {"activeUsers": 0, "sessions": 0, "screenPageViews": 0}
    rows = [(report_date, report.get(report_date, zero)) for report_date in dates]
    yesterday = rows[-1][1]
    return {
        "version": 2,
        "status": "ok",
        "metric": "activeUsers",
        "throughDate": through_date.isoformat(),
        "updatedAt": now.astimezone(SEOUL).replace(microsecond=0).isoformat(),
        "yesterday": {
            "visitors": yesterday["activeUsers"],
            "sessions": yesterday["sessions"],
            "pageViews": yesterday["screenPageViews"],
        },
        "dailyVisitors": [
            {"date": report_date.isoformat(), "visitors": counts["activeUsers"]}
            for report_date, counts in rows
        ],
    }


def validate_summary(summary: object) -> dict:
    if not isinstance(summary, dict):
        raise RuntimeError("visitor stats must be a JSON object")
    expected_keys = {
        "version", "status", "metric", "throughDate", "updatedAt",
        "yesterday", "dailyVisitors",
    }
    if set(summary) != expected_keys:
        raise RuntimeError(f"visitor stats keys mismatch: {set(summary) ^ expected_keys}")
    if summary["version"] != 2 or summary["metric"] != "activeUsers":
        raise RuntimeError("visitor stats version or metric mismatch")
    status = summary["status"]
    if status not in {"collecting", "ok"}:
        raise RuntimeError(f"unsupported visitor stats status: {status}")
    if status == "collecting":
        if any(summary[key] is not None for key in (
            "throughDate", "updatedAt", "yesterday"
        )) or summary["dailyVisitors"] != []:
            raise RuntimeError("collecting visitor stats must not contain measurements")
        return summary

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(summary["throughDate"])):
        raise RuntimeError("visitor stats throughDate is invalid")
    try:
        datetime.fromisoformat(str(summary["updatedAt"]))
    except ValueError as exc:
        raise RuntimeError("visitor stats updatedAt is invalid") from exc

    yesterday = summary["yesterday"]
    expected_yesterday_keys = {"visitors", "sessions", "pageViews"}
    if not isinstance(yesterday, dict) or set(yesterday) != expected_yesterday_keys:
        raise RuntimeError("yesterday structure mismatch")
    if any(not isinstance(yesterday[key], int) or yesterday[key] < 0 for key in yesterday):
        raise RuntimeError("yesterday contains an invalid count")

    daily = summary["dailyVisitors"]
    if not isinstance(daily, list) or len(daily) != DAILY_WINDOW_DAYS:
        raise RuntimeError("dailyVisitors must contain seven values")
    expected_dates = daily_dates(datetime.strptime(summary["throughDate"], "%Y-%m-%d").date())
    for item, expected_date in zip(daily, expected_dates, strict=True):
        if not isinstance(item, dict) or set(item) != {"date", "visitors"}:
            raise RuntimeError("dailyVisitors structure mismatch")
        if item["date"] != expected_date.isoformat():
            raise RuntimeError("dailyVisitors dates are not consecutive")
        if not isinstance(item["visitors"], int) or item["visitors"] < 0:
            raise RuntimeError("dailyVisitors contains an invalid count")
    if daily[-1]["visitors"] != yesterday["visitors"]:
        raise RuntimeError("latest daily visitor count differs from yesterday")
    return summary


def atomic_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Update the public aggregate GA4 visitor summary.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    if args.validate_only:
        validate_summary(json.loads(output.read_text(encoding="utf-8")))
        print(f"VALID visitor_stats={output}")
        return

    property_id = require_property_id(os.environ.get("GA_PROPERTY_ID", ""))
    access_token = os.environ.get("GA_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise RuntimeError("GA_ACCESS_TOKEN is required")
    summary = validate_summary(build_summary(access_token=access_token, property_id=property_id))
    atomic_write(output, summary)
    if summary["status"] == "ok":
        print(
            "UPDATED "
            f"through={summary['throughDate']} "
            f"visitors={summary['yesterday']['visitors']} "
            f"sessions={summary['yesterday']['sessions']} "
            f"page_views={summary['yesterday']['pageViews']}"
        )
    else:
        print(f"UPDATED through={summary['throughDate']} status={summary['status']}")


if __name__ == "__main__":
    main()
