from typing import Annotated

from fastapi import APIRouter, Query

from backend import clock
from backend.deps import ManagerDep, ParamsDep, SessionDep
from backend.load import build_load_report
from backend.schemas import LoadReport

router = APIRouter(prefix="/api/load", tags=["load"])


@router.get("")
def get_load(
    session: SessionDep,
    _manager: ManagerDep,
    params: ParamsDep,
    weeks: Annotated[int, Query(ge=1, le=52, description="How many weeks of history to chart.")] = 12,
) -> LoadReport:
    """Who carries the review work: weekly history, the load rule's numbers now, and waiting requests. Manager only."""
    return build_load_report(session, clock.now(), params, weeks)
