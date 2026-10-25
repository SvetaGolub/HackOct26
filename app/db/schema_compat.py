"""Подгонка старой схемы MySQL под текущие модели (если alembic не догнал)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


def _apply(sync_conn) -> None:
    inspector = inspect(sync_conn)
    tables = set(inspector.get_table_names())

    if "users" not in tables:
        return

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    user_indexes = {i["name"] for i in inspector.get_indexes("users") if i["name"]}

    if "email" in user_cols and "login" not in user_cols:
        logger.warning("schema_compat: users.email → users.login")
        if "uq_users_email" in user_indexes:
            sync_conn.execute(text("ALTER TABLE users DROP INDEX uq_users_email"))
        sync_conn.execute(
            text("ALTER TABLE users CHANGE COLUMN email login VARCHAR(255) NOT NULL")
        )
        sync_conn.execute(text("ALTER TABLE users ADD UNIQUE KEY uq_users_login (login)"))
        user_cols = {c["name"] for c in inspect(sync_conn).get_columns("users")}

    if "telegram_id" not in user_cols:
        logger.warning("schema_compat: add users.telegram_id")
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN telegram_id BIGINT NULL"))
        sync_conn.execute(
            text("ALTER TABLE users ADD UNIQUE KEY uq_users_telegram_id (telegram_id)")
        )

    if "audit_logs" in tables:
        audit_cols = {c["name"] for c in inspect(sync_conn).get_columns("audit_logs")}
        if "actor_email" in audit_cols and "actor_login" not in audit_cols:
            logger.warning("schema_compat: audit_logs.actor_email → actor_login")
            sync_conn.execute(
                text(
                    "ALTER TABLE audit_logs CHANGE COLUMN actor_email "
                    "actor_login VARCHAR(255) NULL"
                )
            )

    if "payment_occurrences" in tables:
        occ_cols = {c["name"] for c in inspect(sync_conn).get_columns("payment_occurrences")}
        if "chat_notified_at" not in occ_cols:
            logger.warning("schema_compat: add payment_occurrences.chat_notified_at")
            sync_conn.execute(
                text(
                    "ALTER TABLE payment_occurrences "
                    "ADD COLUMN chat_notified_at DATETIME(6) NULL"
                )
            )
        if "receipt_name" not in occ_cols:
            logger.warning("schema_compat: add payment_occurrences.receipt_name")
            sync_conn.execute(
                text("ALTER TABLE payment_occurrences ADD COLUMN receipt_name VARCHAR(255) NULL")
            )
        if "receipt_data_url" not in occ_cols:
            logger.warning("schema_compat: add payment_occurrences.receipt_data_url")
            sync_conn.execute(
                text("ALTER TABLE payment_occurrences ADD COLUMN receipt_data_url MEDIUMTEXT NULL")
            )

    # d4 оставил reminder_logs.chat_id; модели ждут user_id
    if "reminder_logs" in tables:
        rem_cols = {c["name"] for c in inspect(sync_conn).get_columns("reminder_logs")}
        if "user_id" not in rem_cols:
            logger.warning("schema_compat: recreate reminder_logs with user_id")
            sync_conn.execute(text("DROP TABLE reminder_logs"))
            sync_conn.execute(
                text(
                    """
                    CREATE TABLE reminder_logs (
                        id INT NOT NULL AUTO_INCREMENT,
                        occurrence_id INT NOT NULL,
                        user_id INT NOT NULL,
                        sent_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                        PRIMARY KEY (id),
                        UNIQUE KEY uq_reminder_once (occurrence_id, user_id),
                        KEY ix_reminder_logs_occurrence_id (occurrence_id),
                        CONSTRAINT fk_reminder_logs_occurrence_id_payment_occurrences
                            FOREIGN KEY (occurrence_id) REFERENCES payment_occurrences (id)
                            ON DELETE CASCADE,
                        CONSTRAINT fk_reminder_logs_user_id_users
                            FOREIGN KEY (user_id) REFERENCES users (id)
                            ON DELETE CASCADE
                    )
                    """
                )
            )

    if "telegram_link_codes" not in inspect(sync_conn).get_table_names():
        logger.warning("schema_compat: create telegram_link_codes")
        sync_conn.execute(
            text(
                """
                CREATE TABLE telegram_link_codes (
                    id INT NOT NULL AUTO_INCREMENT,
                    user_id INT NOT NULL,
                    code_hash VARCHAR(64) NOT NULL,
                    expires_at DATETIME NOT NULL,
                    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_telegram_link_codes_code_hash (code_hash),
                    KEY ix_telegram_link_codes_user_id (user_id),
                    CONSTRAINT fk_telegram_link_codes_user_id_users
                        FOREIGN KEY (user_id) REFERENCES users (id)
                        ON DELETE CASCADE
                )
                """
            )
        )


async def ensure_schema_compat(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(_apply)
