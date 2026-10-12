from fastapi import APIRouter
from sqlalchemy import select

from backend.deps import SessionDep
from backend.models import Developer, Role
from backend.schemas import Person

router = APIRouter(prefix="/api/people", tags=["people"])


@router.get("")
def list_people(session: SessionDep) -> list[Person]:
    """Everyone, manager first, then by name. Open to any viewer: the role switcher needs the full roster."""
    developers = session.scalars(select(Developer).order_by(Developer.role != Role.manager, Developer.name))
    return [Person.model_validate(d) for d in developers]
