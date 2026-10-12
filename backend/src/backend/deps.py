"""Shared FastAPI dependencies: the database session, the current viewer and the rule parameters in effect."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db import get_session
from backend.models import Developer, Role
from backend.params_store import load_params
from backend.rules.params import RuleParams

SessionDep = Annotated[Session, Depends(get_session)]


def get_params(session: SessionDep) -> RuleParams:
    return load_params(session)


ParamsDep = Annotated[RuleParams, Depends(get_params)]


def get_viewer(
    session: SessionDep,
    x_viewer_id: Annotated[int | None, Header(description="Who is viewing. Demo only: there is no real auth.")] = None,
) -> Developer:
    """The person the request is made as. Without the header this is the manager, matching the
    frontend's default before anyone is picked in the role switcher."""
    if x_viewer_id is None:
        viewer = session.scalars(select(Developer).where(Developer.role == Role.manager).order_by(Developer.id)).first()
    else:
        viewer = session.get(Developer, x_viewer_id)
    if viewer is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown viewer")
    return viewer


ViewerDep = Annotated[Developer, Depends(get_viewer)]


def require_manager(viewer: ViewerDep) -> Developer:
    if viewer.role != Role.manager:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the manager can do this")
    return viewer


ManagerDep = Annotated[Developer, Depends(require_manager)]
