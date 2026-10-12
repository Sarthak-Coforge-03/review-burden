import json
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# backend.db builds its engine at import time, so point it at a throwaway database before importing it.
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"
os.environ.pop("AS_OF", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from backend.db import SessionLocal, create_tables  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import Flag  # noqa: E402
from backend.rules.engine import run_engine  # noqa: E402
from backend.seed import DEFAULT_SEED_PATH, TRIAGE_FILENAME, apply_triage, load_seed  # noqa: E402


@pytest.fixture(scope="session")
def seed_data() -> dict[str, Any]:
    return json.loads(DEFAULT_SEED_PATH.read_text())


@pytest.fixture(scope="session")
def triage_data() -> list[dict[str, Any]]:
    return json.loads((DEFAULT_SEED_PATH.parent / TRIAGE_FILENAME).read_text())


@pytest.fixture(scope="session", autouse=True)
def seeded_db(seed_data: dict[str, Any]) -> None:
    """Data only, no flags: engine tests rely on starting from an empty flags table."""
    create_tables()
    with SessionLocal.begin() as session:
        load_seed(session, seed_data)


@pytest.fixture(scope="module")
def demo_flags(triage_data: list[dict[str, Any]]) -> Iterator[None]:
    """The demo's flags and triage, committed for one test module and removed afterwards.

    For API tests, whose requests commit. Other modules expect an empty flags table.
    """
    with SessionLocal.begin() as s:
        run_engine(s)
        apply_triage(s, triage_data)
    yield
    with SessionLocal.begin() as s:
        s.execute(delete(Flag))


@pytest.fixture
def session() -> Iterator[Session]:
    with SessionLocal() as s:
        yield s


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
