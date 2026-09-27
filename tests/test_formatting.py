from garmin_watch_mcp import formatting
from tests import samples


def test_pick_skips_missing_and_null():
    assert formatting.pick({"a": 1, "b": None}, ["b", "a", "c"]) == {"a": 1}
    assert formatting.pick(None, ["a"]) == {}


def test_daily_summary_keeps_curated_fields_only():
    result = formatting.daily_summary("2026-09-26", samples.USER_SUMMARY)
    assert result["date"] == "2026-09-26"
    assert result["totalSteps"] == 8421
    assert "averageSpo2" not in result  # null
    assert "userProfileId" not in result


def test_sleep_flattens_dto_and_scores():
    result = formatting.sleep("2026-09-26", samples.SLEEP)
    assert result["sleepTimeSeconds"] == 26400
    assert result["sleep_score"] == 82
    assert result["start_utc"] == "2026-09-25T23:00:00+00:00"
    assert result["end_utc"] == "2026-09-26T07:00:00+00:00"
    assert result["avgOvernightHrv"] == 48.0
    assert "sleepMovement" not in result
    assert "no_data" not in result


def test_sleep_without_data_is_flagged():
    assert formatting.sleep("2026-09-26", {"dailySleepDTO": {}})["no_data"] is True


def test_hourly_buckets_ignore_gaps():
    result = formatting.heart_rate("2026-09-26", samples.HEART_RATES)
    assert result["restingHeartRate"] == 52
    assert result["hourly"] == [
        {"hour_utc": "2026-09-26T07:00:00+00:00", "min": 60, "avg": 65.0, "max": 70},
        {"hour_utc": "2026-09-26T08:00:00+00:00", "min": 90, "avg": 90.0, "max": 90},
    ]


def test_stress_drops_negative_markers():
    result = formatting.stress("2026-09-26", samples.STRESS)
    assert result["hourly"] == [
        {"hour_utc": "2026-09-26T07:00:00+00:00", "min": 20, "avg": 30.0, "max": 40}
    ]


def test_hourly_tolerates_bad_samples():
    assert formatting.hourly([[], [None, 5], ["x", 5]]) == []
    assert formatting.hourly(None) == []


def test_body_battery_summarises_and_sorts():
    days = formatting.body_battery(samples.BODY_BATTERY)["days"]
    assert [d["date"] for d in days] == ["2026-09-25", "2026-09-26"]
    assert days[1] == {
        "date": "2026-09-26",
        "charged": 55,
        "drained": 30,
        "highest": 90,
        "lowest": 64,
        "latest": 64,
    }
    assert "highest" not in days[0]


def test_hrv_summary_and_missing():
    result = formatting.hrv("2026-09-26", samples.HRV)
    assert result["lastNightAvg"] == 48 and result["status"] == "BALANCED"
    assert "hrvReadings" not in result
    assert formatting.hrv("2026-09-26", None) == {"date": "2026-09-26", "no_data": True}


def test_training_readiness_takes_latest():
    result = formatting.training_readiness("2026-09-26", samples.TRAINING_READINESS)
    assert result["score"] == 64
    assert formatting.training_readiness("2026-09-26", [])["no_data"] is True


def test_activity_list_entry():
    result = formatting.activity(samples.ACTIVITY_RUN)
    assert result["activityType"] == "running"
    assert result["distance"] == 5000.0
    assert "ownerFullName" not in result


def test_activity_detail_merges_summary_dto():
    result = formatting.activity(samples.ACTIVITY_DETAIL)
    assert result["activityType"] == "running"
    assert result["maxHR"] == 172.0
    assert result["activityName"] == "Morning Run"


def test_activities_newest_first():
    result = formatting.activities([samples.ACTIVITY_RIDE, samples.ACTIVITY_RUN])
    assert result["count"] == 2
    assert [a["activityId"] for a in result["activities"]] == [111, 222]


def test_devices_drop_serial_numbers():
    [device] = formatting.devices(samples.DEVICES)["devices"]
    assert device["productDisplayName"] == "Forerunner 965"
    assert "serialNumber" not in device
