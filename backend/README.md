# Backend

FastAPI service for the Review Health Dashboard. Packaged with uv; the importable package is `backend` (source in `src/backend/`).

```bash
uv sync                                               # install dependencies into .venv
uv run python -m backend.seed                         # replace all rows with data/seed.json (or pass a path)
uv run uvicorn backend.main:app --reload --port 8000  # dev server, docs at http://localhost:8000/docs
uv run pytest                                         # tests run against a throwaway SQLite file, never review_health.db
uv add <package>                                      # add a dependency (updates pyproject.toml and uv.lock)
```

In Docker the image installs from `uv.lock` (`uv sync --locked`), so commit `uv.lock` whenever dependencies change.

The frontend's TypeScript types are generated from this API's OpenAPI schema. After changing a route or schema, run `npm run gen:api` in `frontend/review-burden` (it calls `scripts/export_openapi.py`); `tests/test_openapi_export.py` fails until you do.

All routes live under `/api`. The viewer is identified by the `X-Viewer-Id` header; see the root README for how the frontend sets it.

Synthetic data and its ground truth are in `data/` (see `data/README.md`).
