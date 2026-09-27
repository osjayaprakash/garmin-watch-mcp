"""Trim raw Garmin Connect JSON into compact, JSON-serialisable tool results.

Garmin responses are large and undocumented. Each formatter keeps a curated set
of fields and omits any that are missing or null, so a field Garmin drops
simply disappears from the result instead of breaking the tool.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

_SUMMARY_FIELDS = (
    "calendarDate",
    "totalSteps",
    "dailyStepGoal",
    "totalDistanceMeters",
    "floorsAscended",
    "totalKilocalories",
    "activeKilocalories",
    "bmrKilocalories",
    "restingHeartRate",
    "minHeartRate",
    "maxHeartRate",
    "lastSevenDaysAvgRestingHeartRate",
    "averageStressLevel",
    "maxStressLevel",
    "bodyBatteryHighestValue",
    "bodyBatteryLowestValue",
    "bodyBatteryMostRecentValue",
    "bodyBatteryChargedValue",
    "bodyBatteryDrainedValue",
    "moderateIntensityMinutes",
    "vigorousIntensityMinutes",
    "intensityMinutesGoal",
    "averageSpo2",
    "lowestSpo2",
    "avgWakingRespirationValue",
    "sleepingSeconds",
)

_SLEEP_FIELDS = (
    "calendarDate",
    "sleepTimeSeconds",
    "deepSleepSeconds",
    "lightSleepSeconds",
    "remSleepSeconds",
    "awakeSleepSeconds",
    "napTimeSeconds",
    "awakeCount",
    "averageSpO2Value",
    "lowestSpO2Value",
    "averageRespirationValue",
    "avgSleepStress",
    "sleepScoreFeedback",
)

_HRV_FIELDS = (
    "calendarDate",
    "status",
    "weeklyAvg",
    "lastNightAvg",
    "lastNight5MinHigh",
    "feedbackPhrase",
    "baseline",
)

_READINESS_FIELDS = (
    "calendarDate",
    "timestampLocal",
    "score",
    "level",
    "feedbackShort",
    "sleepScore",
    "sleepScoreFactorFeedback",
    "recoveryTime",
    "recoveryTimeFactorFeedback",
    "hrvFactorFeedback",
    "acuteLoad",
    "acwrFactorFeedback",
    "stressHistoryFactorFeedback",
)

_ACTIVITY_FIELDS = (
    "activityId",
    "activityName",
    "startTimeLocal",
    "startTimeGMT",
    "duration",
    "movingDuration",
    "distance",
    "calories",
    "averageHR",
    "maxHR",
    "averageSpeed",
    "maxSpeed",
    "elevationGain",
    "elevationLoss",
    "steps",
    "averageRunningCadenceInStepsPerMinute",
    "aerobicTrainingEffect",
    "anaerobicTrainingEffect",
    "trainingEffectLabel",
    "activityTrainingLoad",
    "vO2MaxValue",
    "description",
)

_DEVICE_FIELDS = (
    "deviceId",
    "productDisplayName",
    "displayName",
    "partNumber",
    "currentFirmwareVersion",
    "deviceStatus",
    "primary",
)


def pick(data: Mapping[str, Any] | None, fields: Iterable[str]) -> dict[str, Any]:
    """Keep `fields` from `data` in order, skipping missing and null values."""
    if not data:
        return {}
    return {name: data[name] for name in fields if data.get(name) is not None}


def _epoch_ms_to_iso(value: Any) -> str | None:
    if not isinstance(value, int | float):
        return None
    return datetime.fromtimestamp(value / 1000, UTC).isoformat()


def hourly(samples: Sequence[Sequence[Any]] | None) -> list[dict[str, Any]]:
    """Collapse [epoch_ms, value] samples into per-hour (UTC) min/avg/max.

    Garmin marks gaps with negative values (-1 off-wrist, -2 activity) or null;
    those are ignored.
    """
    buckets: dict[datetime, list[float]] = defaultdict(list)
    for sample in samples or ():
        if len(sample) < 2:
            continue
        stamp, value = sample[0], sample[1]
        if not isinstance(stamp, int | float) or not isinstance(value, int | float) or value < 0:
            continue
        hour = datetime.fromtimestamp(stamp / 1000, UTC).replace(minute=0, second=0, microsecond=0)
        buckets[hour].append(value)
    return [
        {
            "hour_utc": hour.isoformat(),
            "min": min(values),
            "avg": round(sum(values) / len(values), 1),
            "max": max(values),
        }
        for hour, values in sorted(buckets.items())
    ]


def daily_summary(day: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    return {"date": day, **pick(raw, _SUMMARY_FIELDS)}


def sleep(day: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    dto = raw.get("dailySleepDTO") or {}
    result: dict[str, Any] = {"date": day, **pick(dto, _SLEEP_FIELDS)}
    if not dto.get("sleepTimeSeconds"):
        result["no_data"] = True
    for key, name in (("sleepStartTimestampGMT", "start_utc"), ("sleepEndTimestampGMT", "end_utc")):
        iso = _epoch_ms_to_iso(dto.get(key))
        if iso:
            result[name] = iso
    overall = ((dto.get("sleepScores") or {}).get("overall") or {}).get("value")
    if overall is not None:
        result["sleep_score"] = overall
    for key in ("restingHeartRate", "avgOvernightHrv", "hrvStatus", "bodyBatteryChange"):
        if raw.get(key) is not None:
            result[key] = raw[key]
    return result


def heart_rate(day: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "restingHeartRate",
        "minHeartRate",
        "maxHeartRate",
        "lastSevenDaysAvgRestingHeartRate",
    )
    return {"date": day, **pick(raw, fields), "hourly": hourly(raw.get("heartRateValues"))}


def stress(day: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    fields = ("avgStressLevel", "maxStressLevel")
    return {"date": day, **pick(raw, fields), "hourly": hourly(raw.get("stressValuesArray"))}


def body_battery(days: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    result = []
    for raw in days:
        levels = [
            s[1]
            for s in raw.get("bodyBatteryValuesArray") or ()
            if len(s) > 1 and isinstance(s[1], int | float)
        ]
        entry = pick(raw, ("date", "charged", "drained"))
        if levels:
            entry.update(highest=max(levels), lowest=min(levels), latest=levels[-1])
        result.append(entry)
    result.sort(key=lambda d: d.get("date", ""))
    return {"days": result}


def hrv(day: str, raw: Mapping[str, Any] | None) -> dict[str, Any]:
    summary = (raw or {}).get("hrvSummary")
    if not summary:
        return {"date": day, "no_data": True}
    return {"date": day, **pick(summary, _HRV_FIELDS)}


def training_readiness(day: str, raw: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    if not raw:
        return {"date": day, "no_data": True}
    latest = max(raw, key=lambda r: r.get("timestampLocal") or "")
    return {"date": day, **pick(latest, _READINESS_FIELDS)}


def activity(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Works for list entries and for the single-activity shape (with summaryDTO)."""
    merged = {**raw, **(raw.get("summaryDTO") or {})}
    result = pick(merged, _ACTIVITY_FIELDS)
    kind = raw.get("activityType") or raw.get("activityTypeDTO") or {}
    if kind.get("typeKey"):
        result["activityType"] = kind["typeKey"]
    return result


def activities(raw: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = [activity(a) for a in raw]
    items.sort(key=lambda a: a.get("startTimeGMT") or a.get("startTimeLocal") or "", reverse=True)
    return {"count": len(items), "activities": items}


def devices(raw: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return {"devices": [pick(d, _DEVICE_FIELDS) for d in raw]}
