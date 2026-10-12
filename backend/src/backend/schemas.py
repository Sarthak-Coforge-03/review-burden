"""API request and response models. The frontend's TypeScript types are generated from these."""

from pydantic import BaseModel, ConfigDict

from backend.models import Role


class Person(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: Role
