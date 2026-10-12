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


class RuleCount(BaseModel):
    rule_key: RuleKey
    count: int


class RoleSummary(BaseModel):
    flags: list[RuleCount] = Field(description="Non-dismissed flags in this role, by rule; rules with none are left out.")
    open: int = Field(description="How many of those are still open (not yet acknowledged).")


class PatternOut(BaseModel):
    rule_key: RuleKey
    role: FlagRole
    count: int = Field(description="Non-dismissed flags of this rule inside the window.")
    window_days: int
    pull_requests: list[PullRequestRef]


class PendingReview(BaseModel):
    pull_request: PullRequestRef
    requested_at: datetime
    waiting_hours: float
    stale: bool = Field(description="Waiting longer than the stale_backlog threshold.")


class ReviewActivity(BaseModel):
    window_days: int
    reviews_given: int
    team_reviews: int = Field(description="Reviews by all developers in the window (the manager is not counted).")
    share: float = Field(description="reviews_given / team_reviews, 0 to 1.")
    team_median: float = Field(description="Median reviews per developer in the window.")
    over_median_multiple: bool = Field(
        description="reviews_given is above the load_concentration rule's multiple of the team median."
    )
    prs_opened: int


class PersonProfile(BaseModel):
    person: Person
    as_author: RoleSummary
    as_reviewer: RoleSummary
    patterns: list[PatternOut] = Field(description="Active repeat patterns, computed now; dismissed flags don't count.")
    review_debt: list[PendingReview] = Field(description="Review requests waiting on this person, oldest first.")
    activity: ReviewActivity


class LoadRow(BaseModel):
    person: Person
    weekly: list[int] = Field(description="Reviews per week, aligned with LoadReport.week_starts.")
    reviews: int = Field(description="Reviews in the load window.")
    share: float = Field(description="reviews / team_reviews, 0 to 1.")
    median_multiple: float | None = Field(description="reviews / team_median; null when the median is 0.")
    over_median_multiple: bool
    pending: int = Field(description="Review requests waiting on this person now.")
    oldest_pending_hours: float | None = Field(description="Age of the oldest waiting request; null if none.")


class LoadReport(BaseModel):
    as_of: datetime
    week_starts: list[datetime] = Field(
        description="Oldest first. Each week is the 7 days after its start; the last one ends at as_of."
    )
    window_days: int
    team_reviews: int = Field(description="Reviews by all developers in the window (the manager is not counted).")
    team_median: float
    top2_share: float = Field(description="Share of team_reviews done by the two busiest developers.")
    top2_share_threshold: float
    median_multiple_threshold: float
    concentrated: bool = Field(description="Whether the load_concentration rule fires on these numbers.")
    people: list[LoadRow] = Field(description="Developers, busiest reviewer first.")


class QualityRow(BaseModel):
    person: Person
    reviews: int = Field(description="Reviews submitted in the period, any verdict.")
    approvals: int = Field(description="PRs approved in the period (a re-approval of the same PR counts once).")
    minutes_per_100_lines: float | None = Field(
        description="Median minutes from PR opened to first approval, per 100 changed lines; null with no approvals."
    )
    comments: int
    comments_per_100_lines: float | None = Field(description="Comments per 100 lines of the PRs reviewed.")
    substantive_share: float | None = Field(
        description="Share of comments that are substantive (the rubber_stamp rule's test); null with no comments."
    )
    big_approvals: int = Field(description="Approved PRs at or over the rubber_stamp size threshold.")
    stamped_big_approvals: int = Field(description="Of those, how many the rubber_stamp rule would flag.")
    approved_merged: int = Field(description="Approved PRs merged by as_of.")
    escapes: int = Field(description="Of those, how many needed a revert or hotfix within the escape window.")
    escape_rate: float | None = Field(description="escapes / approved_merged; null when nothing approved was merged.")


class QualityMedians(BaseModel):
    """Medians across developers who have a value; null when nobody does."""

    minutes_per_100_lines: float | None
    comments_per_100_lines: float | None
    substantive_share: float | None
    escape_rate: float | None


class QualityReport(BaseModel):
    as_of: datetime
    since: datetime
    weeks: int
    big_pr_lines: int = Field(description="The rubber_stamp rule's size threshold.")
    escape_window_days: int
    medians: QualityMedians
    people: list[QualityRow] = Field(description="Developers, by name.")


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
