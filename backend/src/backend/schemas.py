"""API request and response models. The frontend's TypeScript types are generated from these."""

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.models import FlagRole, FlagStatus, Role, RuleKey


class Person(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: Role


class PullRequestRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author_id: int


class FlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_key: RuleKey
    status: FlagStatus
    role: FlagRole | None = Field(description="Which side of the review `person` was on; null for team-level flags.")
    person: Person | None
    pull_request: PullRequestRef | None
    occurred_at: datetime
    evidence: dict[str, Any] = Field(description="Rule-specific facts behind the flag; keys depend on `rule_key`.")
    note: str | None
    dismiss_reason: str | None


class FlagUpdate(BaseModel):
    status: FlagStatus
    note: str | None = Field(
        default=None, max_length=2000, description="Omit to keep the current note; null or blank clears it."
    )
    dismiss_reason: str | None = Field(
        default=None, max_length=2000, description="Required when dismissing; cleared for any other status."
    )

    @model_validator(mode="after")
    def dismissing_needs_a_reason(self) -> Self:
        if self.status == FlagStatus.dismissed and not (self.dismiss_reason or "").strip():
            raise ValueError("dismiss_reason is required when dismissing a flag")
        return self
