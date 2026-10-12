from fastapi import APIRouter, HTTPException
from fastapi import status as http
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.deps import ManagerDep, SessionDep, ViewerDep
from backend.models import Flag, FlagStatus, Role, RuleKey
from backend.schemas import FlagOut, FlagUpdate

router = APIRouter(prefix="/api/flags", tags=["flags"])


@router.get("")
def list_flags(
    session: SessionDep,
    viewer: ViewerDep,
    status: FlagStatus | None = None,
    rule_key: RuleKey | None = None,
    person_id: int | None = None,
) -> list[FlagOut]:
    """Flags, newest first. The manager sees all; a developer sees only flags about themselves."""
    if viewer.role != Role.manager:
        if person_id is not None and person_id != viewer.id:
            raise HTTPException(http.HTTP_403_FORBIDDEN, "Developers can only see their own flags")
        person_id = viewer.id

    query = (
        select(Flag)
        .options(selectinload(Flag.person), selectinload(Flag.pull_request))
        .order_by(Flag.occurred_at.desc(), Flag.id)
    )
    if status is not None:
        query = query.where(Flag.status == status)
    if rule_key is not None:
        query = query.where(Flag.rule_key == rule_key)
    if person_id is not None:
        query = query.where(Flag.person_id == person_id)
    return [FlagOut.model_validate(flag) for flag in session.scalars(query)]


@router.patch("/{flag_id}")
def triage_flag(flag_id: int, update: FlagUpdate, session: SessionDep, _manager: ManagerDep) -> FlagOut:
    """Acknowledge, dismiss (with a reason) or reopen a flag, and optionally set its note."""
    flag = session.get(Flag, flag_id)
    if flag is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND, "Flag not found")

    flag.status = update.status
    flag.dismiss_reason = update.dismiss_reason.strip() if update.status == FlagStatus.dismissed else None
    if "note" in update.model_fields_set:
        flag.note = (update.note or "").strip() or None
    session.commit()
    return FlagOut.model_validate(flag)
