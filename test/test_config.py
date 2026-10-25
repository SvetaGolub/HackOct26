from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest
from pydantic import ValidationError

from app.config import Settings, settings
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


def test_settings_require_strong_secrets():
    common = {
        "TELEGRAM_BOT_TOKEN": "test-token",
        "DATABASE_URL": "mysql+aiomysql://app:private-password@localhost/app",
        "JWT_SECRET_KEY": "a-unique-signing-secret-with-at-least-32-bytes",
        "ADMIN_PASSWORD": "AdminPassword123",
    }

    assert Settings(_env_file=None, **common).API_DOCS_ENABLED is False

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(common | {"JWT_SECRET_KEY": "short"}))

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(common | {"ADMIN_PASSWORD": "short"}))

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(common | {"CORS_ORIGINS": "*"}))


def test_api_documentation_is_disabled_by_default():
    from app.main import app

    assert app.openapi_url is None
    assert not any(
        getattr(route, "path", None) in {"/api/v1/docs", "/api/v1/openapi.json"}
        for route in app.routes
    )
