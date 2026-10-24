from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from app.config import settings
from app.db.services import schedule


def test_payment_date_uses_configured_timezone(monkeypatch):
    class FixedDateTime:
        @staticmethod
        def now(tz):
            assert tz == ZoneInfo("Europe/Moscow")
            return datetime(2026, 10, 24, 21, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(settings, "TIMEZONE", "Europe/Moscow")
    monkeypatch.setattr(schedule, "datetime", FixedDateTime)

    assert schedule.today_local().isoformat() == "2026-10-25"


def test_invalid_configured_timezone_is_not_silently_ignored(monkeypatch):
    monkeypatch.setattr(settings, "TIMEZONE", "Not/A_Timezone")

    with pytest.raises(ZoneInfoNotFoundError):
        schedule.today_local()
