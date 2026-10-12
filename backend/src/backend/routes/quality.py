from typing import Annotated

from fastapi import APIRouter, Query

from backend import clock
from backend.deps import ManagerDep, ParamsDep, SessionDep
from backend.quality import build_quality_report
from backend.schemas import QualityReport

router = APIRouter(prefix="/api/quality", tags=["quality"])


@router.get("")
def get_quality(
    session: SessionDep,
    _manager: ManagerDep,
    params: ParamsDep,
    weeks: Annotated[int, Query(ge=1, le=52, description="How many weeks of reviews to include.")] = 12,
) -> QualityReport:
    """Per reviewer: approval speed, comment depth, rubber stamps and escapes, with team medians. Manager only."""
    return build_quality_report(session, clock.now(), params, weeks)
