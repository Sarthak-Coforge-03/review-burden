"""FastAPI application: CORS and route registration. All routes live under /api."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.db import create_tables
from backend.routes import demo, flags, load, overview, people, quality, settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    create_tables()
    yield


app = FastAPI(title="Review Health Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(people.router)
app.include_router(flags.router)
app.include_router(load.router)
app.include_router(quality.router)
app.include_router(overview.router)
app.include_router(settings.router)
app.include_router(demo.router)


class HealthResponse(BaseModel):
    status: str


@app.get("/api/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")
