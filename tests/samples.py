"""Trimmed Garmin Connect responses, using the API's JSON field names."""

# 2026-09-26 07:00:00 UTC in epoch milliseconds.
T0 = 1790406000000
MIN = 60_000

USER_SUMMARY = {
    "calendarDate": "2026-09-26",
    "totalSteps": 8421,
    "dailyStepGoal": 10000,
    "totalDistanceMeters": 6512,
    "restingHeartRate": 52,
    "averageStressLevel": 31,
    "bodyBatteryMostRecentValue": 64,
    "averageSpo2": None,
    "userProfileId": 123456,
    "privacyProtected": False,
}

SLEEP = {
    "dailySleepDTO": {
        "calendarDate": "2026-09-26",
        "sleepTimeSeconds": 26400,
        "deepSleepSeconds": 5400,
        "lightSleepSeconds": 14400,
        "remSleepSeconds": 6600,
        "awakeSleepSeconds": 900,
        "sleepStartTimestampGMT": T0 - 8 * 60 * MIN,
        "sleepEndTimestampGMT": T0,
        "sleepScores": {"overall": {"value": 82, "qualifierKey": "GOOD"}},
    },
    "sleepMovement": [{"startGMT": "2026-09-25T23:00:00.0", "activityLevel": 1.2}] * 50,
    "restingHeartRate": 51,
    "avgOvernightHrv": 48.0,
    "bodyBatteryChange": 55,
}

HEART_RATES = {
    "restingHeartRate": 52,
    "minHeartRate": 48,
    "maxHeartRate": 141,
    "heartRateValues": [
        [T0, 60],
        [T0 + 2 * MIN, 70],
        [T0 + 4 * MIN, None],
        [T0 + 60 * MIN, 90],
    ],
}

STRESS = {
    "avgStressLevel": 31,
    "maxStressLevel": 88,
    "stressValuesArray": [[T0, 20], [T0 + 3 * MIN, -1], [T0 + 6 * MIN, 40], [T0 + 61 * MIN, -2]],
}

BODY_BATTERY = [
    {
        "date": "2026-09-26",
        "charged": 55,
        "drained": 30,
        "bodyBatteryValuesArray": [[T0, 90], [T0 + 60 * MIN, 70], [T0 + 120 * MIN, 64]],
    },
    {"date": "2026-09-25", "charged": 40, "drained": 60, "bodyBatteryValuesArray": []},
]

HRV = {
    "hrvSummary": {
        "calendarDate": "2026-09-26",
        "weeklyAvg": 50,
        "lastNightAvg": 48,
        "lastNight5MinHigh": 70,
        "baseline": {"lowUpper": 42, "balancedLow": 45, "balancedUpper": 58},
        "status": "BALANCED",
        "feedbackPhrase": "HRV_BALANCED_2",
    },
    "hrvReadings": [{"hrvValue": 40}] * 100,
}

TRAINING_READINESS = [
    {
        "calendarDate": "2026-09-26",
        "timestampLocal": "2026-09-26T06:30:00.0",
        "score": 71,
        "level": "HIGH",
    },
    {
        "calendarDate": "2026-09-26",
        "timestampLocal": "2026-09-26T12:00:00.0",
        "score": 64,
        "level": "MODERATE",
    },
]

ACTIVITY_RUN = {
    "activityId": 111,
    "activityName": "Morning Run",
    "activityType": {"typeKey": "running", "typeId": 1},
    "startTimeLocal": "2026-09-26 06:00:00",
    "startTimeGMT": "2026-09-26 13:00:00",
    "duration": 1800.5,
    "distance": 5000.0,
    "averageHR": 150.0,
    "ownerFullName": "Private Person",
}

ACTIVITY_RIDE = {
    "activityId": 222,
    "activityName": "Evening Ride",
    "activityType": {"typeKey": "cycling"},
    "startTimeGMT": "2026-09-25 23:00:00",
    "distance": 20000.0,
}

ACTIVITY_DETAIL = {
    "activityId": 111,
    "activityName": "Morning Run",
    "activityTypeDTO": {"typeKey": "running"},
    "summaryDTO": {
        "startTimeLocal": "2026-09-26T06:00:00.0",
        "startTimeGMT": "2026-09-26T13:00:00.0",
        "duration": 1800.5,
        "distance": 5000.0,
        "averageHR": 150.0,
        "maxHR": 172.0,
        "elevationGain": 42.0,
    },
}

DEVICES = [
    {
        "deviceId": 3333,
        "productDisplayName": "Forerunner 965",
        "currentFirmwareVersion": "21.19",
        "serialNumber": "SECRET-SN",
        "imageUrl": "https://example.com/x.png",
    },
]
