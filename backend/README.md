# Backend

FastAPI service for the Review Health Dashboard. Packaged with uv; the importable package is `backend` (source in `src/backend/`).

```bash
uv sync                                               # install dependencies into .venv
uv run uvicorn backend.main:app --reload --port 8000  # dev server, docs at http://localhost:8000/docs
uv add <package>                                      # add a dependency (updates pyproject.toml and uv.lock)
```

In Docker the image installs from `uv.lock` (`uv sync --locked`), so commit `uv.lock` whenever dependencies change.

All routes live under `/api`. The viewer is identified by the `X-Viewer-Id` header; see the root README for how the frontend sets it.

Synthetic data and its ground truth are in `data/` (see `data/README.md`).
