import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import feedback as feedback_api
from app.db.models.enum import Currency, Periodicity, UserRole
from app.db.schemas.feedback import FeedbackCreate


def _payload() -> FeedbackCreate:
    return FeedbackCreate(
        employee="Иван Иванов",
        department="Бухгалтерия",
        request="Нужно согласовать оплату сервера",
        amount=Decimal("1234.50"),
        currency=Currency.RUB,
        due_date=date(2026, 11, 1),
        periodicity=Periodicity.CUSTOM,
        interval_days=7,
    )


def test_feedback_is_sent_to_linked_admin(monkeypatch):
    async def scenario():
        sent = []

        async def send_message(chat_id, text):
            sent.append((chat_id, text))

        class FakeDB:
            async def execute(self, _statement):
                return SimpleNamespace(
                    scalars=lambda: SimpleNamespace(all=lambda: [987654321])
                )

            def add(self, _record):
                pass

            async def commit(self):
                pass

        monkeypatch.setattr(feedback_api.bot, "send_message", send_message)
        monkeypatch.setattr(feedback_api.settings, "ADMIN_TELEGRAM_CHAT_ID", "")
        user = SimpleNamespace(id=5, login="ivan", role=UserRole.USER)

        response = await feedback_api.submit_feedback(_payload(), FakeDB(), user)

        assert response.message == "Обращение отправлено администратору"
        assert len(sent) == 1
        assert sent[0][0] == "987654321"
        assert "Пользователь: ivan" in sent[0][1]
        assert "Запрос: Нужно согласовать оплату сервера" in sent[0][1]
        assert "Периодичность: Раз в 7 дн." in sent[0][1]

    asyncio.run(scenario())


def test_feedback_uses_configured_admin_chat(monkeypatch):
    async def scenario():
        sent = []

        async def send_message(chat_id, _text):
            sent.append(chat_id)

        class FakeDB:
            async def execute(self, _statement):
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

            def add(self, _record):
                pass

            async def commit(self):
                pass

        monkeypatch.setattr(feedback_api.bot, "send_message", send_message)
        monkeypatch.setattr(
            feedback_api.settings, "ADMIN_TELEGRAM_CHAT_ID", "@invoice_admin"
        )
        user = SimpleNamespace(id=5, login="ivan", role=UserRole.USER)

        await feedback_api.submit_feedback(_payload(), FakeDB(), user)

        assert sent == ["@invoice_admin"]

    asyncio.run(scenario())


def test_feedback_falls_back_to_configured_telegram_chat(monkeypatch):
    async def scenario():
        sent = []

        async def send_message(chat_id, _text):
            sent.append(chat_id)

        class FakeDB:
            async def execute(self, _statement):
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

            def add(self, _record):
                pass

            async def commit(self):
                pass

        monkeypatch.setattr(feedback_api.bot, "send_message", send_message)
        monkeypatch.setattr(feedback_api.settings, "ADMIN_TELEGRAM_CHAT_ID", "")
        monkeypatch.setattr(feedback_api.settings, "TELEGRAM_CHAT_ID", "-1001234567890")
        user = SimpleNamespace(id=5, login="ivan", role=UserRole.USER)

        await feedback_api.submit_feedback(_payload(), FakeDB(), user)

        assert sent == ["-1001234567890"]

    asyncio.run(scenario())


def test_feedback_reports_missing_admin_recipient(monkeypatch):
    async def scenario():
        class FakeDB:
            async def execute(self, _statement):
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

        async def send_message(_chat_id, _text):
            pytest.fail("Telegram must not be called without an administrator recipient")

        monkeypatch.setattr(feedback_api.bot, "send_message", send_message)
        monkeypatch.setattr(feedback_api.settings, "ADMIN_TELEGRAM_CHAT_ID", "")
        monkeypatch.setattr(feedback_api.settings, "TELEGRAM_CHAT_ID", "")
        user = SimpleNamespace(id=5, login="ivan", role=UserRole.USER)

        with pytest.raises(HTTPException) as error:
            await feedback_api._send_feedback(_payload(), user, FakeDB())

        assert error.value.status_code == 503

    asyncio.run(scenario())


def test_feedback_rejects_admin_user():
    async def scenario():
        user = SimpleNamespace(id=1, login="admin", role=UserRole.ADMIN)

        with pytest.raises(HTTPException) as error:
            await feedback_api.submit_feedback(_payload(), object(), user)

        assert error.value.status_code == 403

    asyncio.run(scenario())


def test_telegram_message_chunks_respect_utf16_limit():
    message = "🙂" * 4500
    chunks = feedback_api._split_telegram_message(message)

    assert "".join(chunks) == message
    assert all(len(chunk.encode("utf-16-le")) // 2 <= 4000 for chunk in chunks)
