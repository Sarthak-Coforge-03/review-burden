"""The frontend's committed OpenAPI schema must match the API, or its generated types are stale."""

import json
from pathlib import Path

from backend.main import app

COMMITTED = Path(__file__).resolve().parents[2] / "frontend" / "review-burden" / "lib" / "openapi.json"


def test_frontend_schema_is_up_to_date():
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    assert committed == app.openapi(), "API changed: run `npm run gen:api` in frontend/review-burden"
