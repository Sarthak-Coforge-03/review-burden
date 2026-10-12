# Review Health Dashboard

Shows whether code review is working on a team and whether review work is shared fairly. Every flag is produced by a deterministic rule and shows its evidence.

## Run with Docker

Prerequisite: Docker Desktop running. Run every command from this folder (`review-burden/`).

```bash
docker compose up --build -d        # build both images and start them in the background (api seeds itself)
docker compose ps                   # both services should be "Up"; api should be "healthy"
docker compose logs -f              # follow logs (Ctrl+C stops following, not the app)
docker compose down                 # stop and remove the containers (data is kept)
```

Then open:

| URL | What |
|---|---|
| http://localhost:3000 | Web app |
| http://localhost:8000/api/health | API health check, returns `{"status":"ok"}` |
| http://localhost:8000/docs | Interactive API docs (Swagger) |

Other useful commands:

```bash
docker compose up --build -d web    # rebuild and restart only the frontend after changes
docker compose up --build -d api    # rebuild and restart only the backend after changes
docker compose logs -f api          # logs for one service
docker compose exec api sh          # shell inside the running api container
docker compose down -v              # stop AND delete the SQLite volume (wipes all data)
docker compose restart api          # reset the demo data (reseeds on start)
docker compose run --rm api python -m backend.seed   # reseed without restarting the api
```

The api container runs the seed every time it starts, replacing every row with `backend/data/seed.json`. Anything changed in the app (dismissed flags, edited thresholds) is lost on restart. The seed file is baked into the api image; rebuild the image after regenerating the data.

The images run production builds, so code changes need a rebuild (`--build`). For fast edit-and-refresh, run the services locally instead.

## Run locally without Docker

Backend (Python 3.12 via [uv](https://docs.astral.sh/uv/)):

```bash
cd backend
uv sync
uv run python -m backend.seed       # creates review_health.db in backend/ with the demo data
uv run uvicorn backend.main:app --reload --port 8000
```

Frontend (Node 24):

```bash
cd frontend/review-burden
npm install
npm run dev                         # http://localhost:3000, talks to the API on localhost:8000
```

## Configuration

| Variable | Service | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | api | `sqlite:////data/review_health.db` in Docker | SQLite file, stored on the `db-data` volume |
| `CORS_ORIGINS` | api | `http://localhost:3000` | Comma-separated origins allowed to call the API from a browser |
| `AS_OF` | api | `2026-10-09T18:00:00Z` (the synthetic data's `as_of`) | What the rules treat as "now". An ISO 8601 timestamp, or `wall` for the real clock |
| `API_URL` | web | `http://api:8000` in Docker, else `http://localhost:8000` | Where server-side Next.js code calls the API |
| `NEXT_PUBLIC_API_URL` | web (build arg) | `http://localhost:8000` | API address baked into browser code at build time; changing it needs a rebuild |

## Viewing as someone (no real auth)

The header's "Viewing as" switcher stores the chosen person's id in a `viewer_id` cookie. Server-side API calls forward it as the `X-Viewer-Id` header, and the API decides what that viewer may see. Picking a developer opens their own page (`/me`); picking the manager opens the team overview.

The switcher lists people from `GET /api/people`. Until that endpoint exists it shows "API unavailable"; this is expected on the current skeleton.

## Layout

```
review-burden/
├── docker-compose.yml          # api (:8000) + web (:3000), SQLite on the db-data volume
├── backend/                    # FastAPI, uv project, package `backend` under src/
│   ├── src/backend/main.py     # app, CORS, routes
│   ├── data/                   # deterministic synthetic data (see data/README.md)
│   └── scripts/                # data generator
└── frontend/review-burden/     # Next.js 16 (App Router), Tailwind + DaisyUI
    ├── app/                    # pages: overview, flags, load, quality, people, settings, me
    ├── components/             # header, nav, role switcher
    └── lib/                    # server-only API client and viewer cookie helpers
```
