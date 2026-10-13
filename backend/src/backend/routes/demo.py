from fastapi import APIRouter
from sqlalchemy import func, select

from backend.deps import ManagerDep, SessionDep
from backend.models import Flag, FlagStatus
from backend.schemas import DemoReset
from backend.seed import read_seed_files, seed_demo

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset")
def reset_demo(session: SessionDep, _manager: ManagerDep) -> DemoReset:
    """Replace everything with the demo, as `python -m backend.seed` does: the demo data, the flags the rules
    find with the default settings, and the starting triage. Triage and saved settings are lost. Manager only."""
    data, triage = read_seed_files()
    result = seed_demo(session, data, triage)
    session.commit()
    count = select(func.count()).select_from(Flag)
    return DemoReset(
        rows=result.rows,
        flags=session.scalar(count),
        open_flags=session.scalar(count.where(Flag.status == FlagStatus.open)),
    )
