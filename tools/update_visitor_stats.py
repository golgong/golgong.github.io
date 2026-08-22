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
PRIVACY_THRESHOLD = 5


def require_property_id(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"\d+", value):
        raise RuntimeError("GA_PROPERTY_ID must contain digits only")
    return value


def request_report(
    *, access_token: str, property_id: str, start_date: date, end_date: date,
    metrics: tuple[str, ...],
) -> dict[str, int]:
    body = json.dumps(
        {
            "dateRanges": [
                {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}
            ],
            "metrics": [{"name": name} for name in metrics],
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
            "User-Agent": "golgong-visitor-stats/1.0",
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

    headers = [item.get("name") for item in payload.get("metricHeaders", [])]
    if headers != list(metrics):
        raise RuntimeError(f"unexpected metric headers: {headers}")
    rows = payload.get("rows", [])
    if not rows:
        return {name: 0 for name in metrics}
    if len(rows) != 1:
        raise RuntimeError(f"expected one aggregate row, got {len(rows)}")
    values = rows[0].get("metricValues", [])
    if len(values) != len(metrics):
        raise RuntimeError("metric value count mismatch")
    result: dict[str, int] = {}
    for name, item in zip(metrics, values, strict=True):
        raw = str(item.get("value", ""))
        if not re.fullmatch(r"\d+", raw):
            raise RuntimeError(f"unexpected value for {name}: {raw!r}")
        result[name] = int(raw)
    return result


def weekly_periods(through_date: date) -> list[tuple[date, date]]:
    periods = []
    for weeks_ago in range(3, -1, -1):
        end_date = through_date - timedelta(days=7 * weeks_ago)
        periods.append((end_date - timedelta(days=6), end_date))
    return periods


def build_summary(*, access_token: str, property_id: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(SEOUL)
    if now.tzinfo is None:
        raise RuntimeError("now must be timezone-aware")
    through_date = now.astimezone(SEOUL).date() - timedelta(days=2)
    periods = weekly_periods(through_date)
    weekly: list[int] = []
    current_page_views = 0
    for index, (start_date, end_date) in enumerate(periods):
        metrics = ("activeUsers", "screenPageViews") if index == 3 else ("activeUsers",)
        report = request_report(
            access_token=access_token,
            property_id=property_id,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
        )
        weekly.append(report["activeUsers"])
        if index == 3:
            current_page_views = report["screenPageViews"]

    current = weekly[-1]
    previous = weekly[-2]
    base = {
        "version": 1,
        "status": "low_volume" if current < PRIVACY_THRESHOLD else "ok",
        "metric": "activeUsers",
        "throughDate": through_date.isoformat(),
        "updatedAt": now.astimezone(SEOUL).replace(microsecond=0).isoformat(),
        "current7Days": None,
        "previous7Days": None,
        "changeVisitors": None,
        "weeklyVisitors": [],
    }
    if current < PRIVACY_THRESHOLD:
        return base

    base["current7Days"] = {"visitors": current, "pageViews": current_page_views}
    if previous >= PRIVACY_THRESHOLD:
        base["previous7Days"] = {"visitors": previous}
        base["changeVisitors"] = current - previous
    base["weeklyVisitors"] = [value if value >= PRIVACY_THRESHOLD else None for value in weekly]
    return base


def validate_summary(summary: object) -> dict:
    if not isinstance(summary, dict):
        raise RuntimeError("visitor stats must be a JSON object")
    expected_keys = {
        "version", "status", "metric", "throughDate", "updatedAt",
        "current7Days", "previous7Days", "changeVisitors", "weeklyVisitors",
    }
    if set(summary) != expected_keys:
        raise RuntimeError(f"visitor stats keys mismatch: {set(summary) ^ expected_keys}")
    if summary["version"] != 1 or summary["metric"] != "activeUsers":
        raise RuntimeError("visitor stats version or metric mismatch")
    status = summary["status"]
    if status not in {"collecting", "low_volume", "ok"}:
        raise RuntimeError(f"unsupported visitor stats status: {status}")
    if status == "collecting":
        if any(summary[key] is not None for key in (
            "throughDate", "updatedAt", "current7Days", "previous7Days", "changeVisitors"
        )) or summary["weeklyVisitors"] != []:
            raise RuntimeError("collecting visitor stats must not contain measurements")
        return summary

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(summary["throughDate"])):
        raise RuntimeError("visitor stats throughDate is invalid")
    try:
        datetime.fromisoformat(str(summary["updatedAt"]))
    except ValueError as exc:
        raise RuntimeError("visitor stats updatedAt is invalid") from exc

    if status == "low_volume":
        if any(summary[key] is not None for key in (
            "current7Days", "previous7Days", "changeVisitors"
        )) or summary["weeklyVisitors"] != []:
            raise RuntimeError("low-volume visitor stats must suppress measurements")
        return summary

    current = summary["current7Days"]
    if not isinstance(current, dict) or set(current) != {"visitors", "pageViews"}:
        raise RuntimeError("current7Days structure mismatch")
    if any(not isinstance(current[key], int) or current[key] < 0 for key in current):
        raise RuntimeError("current7Days contains an invalid count")
    if current["visitors"] < PRIVACY_THRESHOLD:
        raise RuntimeError("exact visitor count is below the privacy threshold")

    previous = summary["previous7Days"]
    change = summary["changeVisitors"]
    if previous is None:
        if change is not None:
            raise RuntimeError("changeVisitors requires previous7Days")
    else:
        if not isinstance(previous, dict) or set(previous) != {"visitors"}:
            raise RuntimeError("previous7Days structure mismatch")
        if not isinstance(previous["visitors"], int) or previous["visitors"] < PRIVACY_THRESHOLD:
            raise RuntimeError("previous7Days contains an invalid count")
        if change != current["visitors"] - previous["visitors"]:
            raise RuntimeError("changeVisitors arithmetic mismatch")

    weekly = summary["weeklyVisitors"]
    if not isinstance(weekly, list) or len(weekly) != 4:
        raise RuntimeError("weeklyVisitors must contain four values")
    if any(value is not None and (not isinstance(value, int) or value < PRIVACY_THRESHOLD) for value in weekly):
        raise RuntimeError("weeklyVisitors contains an invalid count")
    if weekly[-1] != current["visitors"]:
        raise RuntimeError("latest weeklyVisitors value differs from current7Days")
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
            f"visitors={summary['current7Days']['visitors']} "
            f"page_views={summary['current7Days']['pageViews']} "
            f"change={summary['changeVisitors']}"
        )
    else:
        print(f"UPDATED through={summary['throughDate']} status={summary['status']}")


if __name__ == "__main__":
    main()
