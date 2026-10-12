"""FastAPI application: CORS and route registration. All routes live under /api."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db import create_tables, get_session
from backend.models import Developer, Role

SessionDep = Annotated[Session, Depends(get_session)]


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


class HealthResponse(BaseModel):
    status: str


class Person(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: Role


@app.get("/api/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/people")
def list_people(session: SessionDep) -> list[Person]:
    """Everyone, manager first, then by name. Open to any viewer: the role switcher needs the full roster."""
    developers = session.scalars(select(Developer).order_by(Developer.role != Role.manager, Developer.name))
    return [Person.model_validate(d) for d in developers]
