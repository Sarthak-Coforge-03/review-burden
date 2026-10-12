from fastapi import APIRouter, HTTPException
from fastapi import status as http
from sqlalchemy import select

from backend import clock
from backend.deps import ManagerDep, SessionDep, ViewerDep
from backend.models import Developer, Role
from backend.profiles import build_profiles
from backend.rules.params import DEFAULT_PARAMS
from backend.schemas import Person, PersonProfile

router = APIRouter(prefix="/api/people", tags=["people"])


@router.get("")
def list_people(session: SessionDep) -> list[Person]:
    """Everyone, manager first, then by name. Open to any viewer: the role switcher needs the full roster."""
    developers = session.scalars(select(Developer).order_by(Developer.role != Role.manager, Developer.name))
    return [Person.model_validate(d) for d in developers]


@router.get("/profiles")
def list_profiles(session: SessionDep, _manager: ManagerDep) -> list[PersonProfile]:
    """Every developer's profile, by name. Manager only."""
    developers = session.scalars(select(Developer).where(Developer.role == Role.dev).order_by(Developer.name)).all()
    return build_profiles(session, developers, clock.now(), DEFAULT_PARAMS)


@router.get("/{person_id}/profile")
def get_profile(person_id: int, session: SessionDep, viewer: ViewerDep) -> PersonProfile:
    """One person's profile. The manager can see anyone's; a developer only their own."""
    if viewer.role != Role.manager and viewer.id != person_id:
        raise HTTPException(http.HTTP_403_FORBIDDEN, "Developers can only see their own profile")
    person = session.get(Developer, person_id)
    if person is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND, "Person not found")
    [profile] = build_profiles(session, [person], clock.now(), DEFAULT_PARAMS)
    return profile
