"""Database engine, sessions and the declarative base. SQLite in WAL mode with foreign keys enforced."""

import enum
import os
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import DateTime, Engine, Enum, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Stores naive UTC (SQLite has no time zones) and always returns aware UTC, so values
    compare cleanly with `clock.now()`. Rejects naive input rather than guessing its zone."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"naive datetime {value!r}; pass a time-zone-aware value")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    type_annotation_map = {
        datetime: UTCDateTime(),
        enum.Enum: Enum(enum.Enum, validate_strings=True),
    }


def make_engine(url: str) -> Engine:
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = make_engine(os.environ.get("DATABASE_URL", "sqlite:///review_health.db"))
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with SessionLocal() as session:
        yield session


def create_tables(bind: Engine = engine) -> None:
    from backend import models  # noqa: F401  registers the tables on Base.metadata

    Base.metadata.create_all(bind)
