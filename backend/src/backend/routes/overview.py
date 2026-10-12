from typing import Annotated

from fastapi import APIRouter, Query

from backend import clock
from backend.deps import ManagerDep, SessionDep
from backend.health import build_overview
from backend.rules.params import DEFAULT_PARAMS
from backend.schemas import Overview

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("")
def get_overview(
    session: SessionDep,
    _manager: ManagerDep,
    weeks: Annotated[int, Query(ge=1, le=52, description="How many weeks of score history to include.")] = 12,
) -> Overview:
    """Team health score with its five parts, KPI tiles and the weekly score trend. Manager only."""
    return build_overview(session, clock.now(), DEFAULT_PARAMS, weeks)
