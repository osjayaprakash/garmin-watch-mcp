"""A scriptable stand-in for garmin_watch_mcp.core.client.GarminClient."""

from __future__ import annotations

import asyncio

from tests import samples


class FakeGarminClient:
    """Records calls; `fail_next[method]` holds exceptions to raise, one per call."""

    def __init__(self, *, auth_delay: float = 0.0):
        self.auth_delay = auth_delay
        self.calls: list[tuple] = []
        self.fail_next: dict[str, list[Exception]] = {}
        self.by_date_result = [samples.ACTIVITY_RUN, samples.ACTIVITY_RIDE]

    def _record(self, method: str, *args) -> None:
        self.calls.append((method, *args))
        queue = self.fail_next.get(method)
        if queue:
            raise queue.pop(0)

    def count(self, method: str) -> int:
        return sum(1 for call in self.calls if call[0] == method)

    async def authenticate(self) -> None:
        if self.auth_delay:
            await asyncio.sleep(self.auth_delay)
        self._record("authenticate")

    async def user_summary(self, day):
        self._record("user_summary", day)
        return {**samples.USER_SUMMARY, "calendarDate": day}

    async def sleep(self, day):
        self._record("sleep", day)
        return samples.SLEEP

    async def heart_rates(self, day):
        self._record("heart_rates", day)
        return samples.HEART_RATES

    async def stress(self, day):
        self._record("stress", day)
        return samples.STRESS

    async def body_battery(self, start, end):
        self._record("body_battery", start, end)
        return samples.BODY_BATTERY

    async def hrv(self, day):
        self._record("hrv", day)
        return samples.HRV

    async def training_readiness(self, day):
        self._record("training_readiness", day)
        return samples.TRAINING_READINESS

    async def activities(self, start, limit):
        self._record("activities", start, limit)
        return [samples.ACTIVITY_RUN, samples.ACTIVITY_RIDE][:limit]

    async def activities_by_date(self, start, end):
        self._record("activities_by_date", start, end)
        return list(self.by_date_result)

    async def activity(self, activity_id):
        self._record("activity", activity_id)
        return samples.ACTIVITY_DETAIL

    async def devices(self):
        self._record("devices")
        return samples.DEVICES
