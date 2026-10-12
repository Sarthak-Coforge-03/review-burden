from typing import Annotated

from fastapi import APIRouter, Query

from backend import clock
from backend.deps import ManagerDep, ParamsDep, SessionDep
from backend.health import build_overview
from backend.schemas import Overview

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("")
def get_overview(
    session: SessionDep,
    _manager: ManagerDep,
    params: ParamsDep,
    weeks: Annotated[int, Query(ge=1, le=52, description="How many weeks of score history to include.")] = 12,
) -> Overview:
    """Team health score with its five parts, KPI tiles and the weekly score trend. Manager only."""
    return build_overview(session, clock.now(), params, weeks)
