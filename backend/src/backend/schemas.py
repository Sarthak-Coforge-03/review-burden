"""API request and response models. The frontend's TypeScript types are generated from these."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class HealthPartKey(StrEnum):
    coverage = "coverage"
    depth = "depth"
    escapes = "escapes"
    responsiveness = "responsiveness"
    load_balance = "load_balance"


class HealthPart(BaseModel):
    """One part of the health score. `good` of `total` went well; how that maps to `score` depends on the part."""

    key: HealthPartKey
    weight: float
    good: int = Field(
        description="coverage: merged PRs approved by someone other than the author before merging; "
        "depth: big-PR approvals that are not rubber stamps; escapes: approved merged PRs with no revert or hotfix; "
        "responsiveness: review requests answered (or the PR merged) within the stale threshold; "
        "load_balance: reviews done by everyone except the two busiest developers."
    )
    total: int
    score: int | None = Field(
        description="0-100; null when there was nothing to measure, and the other parts share its weight."
    )


class HealthSnapshot(BaseModel):
    as_of: datetime
    score: int | None = Field(
        description="Weighted average of the parts' scores, 0-100; null when no part could be measured."
    )


class OverviewKpis(BaseModel):
    open_flags: int = Field(description="Flags not yet acknowledged or dismissed, at any age.")
    prs_merged: int = Field(description="PRs merged in the window.")
    median_hours_to_first_review: float | None = Field(
        description="PRs opened in the window: median hours until someone other than the author reviewed."
    )
    waiting_reviews: int = Field(description="Review requests still unanswered on unmerged PRs.")
    stale_reviews: int = Field(description="Of those, how many have waited past the stale threshold.")


class Overview(BaseModel):
    as_of: datetime
    since: datetime
    window_days: int
    escape_rate_floor: float = Field(description="An escape rate at or above this scores 0 on the escapes part.")
    top2_share_threshold: float = Field(description="Load balance scores 100 while the top two do at most this share.")
    stale_after_hours: int = Field(description="Responsiveness counts a request answered within this many hours.")
    score: int | None
    parts: list[HealthPart]
    kpis: OverviewKpis
    trend: list[HealthSnapshot] = Field(
        description="The score as it stood at the end of each of the last `weeks` weeks, oldest first. "
        "Earlier weeks whose window starts before the first PR are left out; the last point is always `as_of`."
    )


class RuleSettings(BaseModel):
    """Every rule threshold and health score weight; the same fields as the backend's RuleParams."""

    rubber_stamp_min_lines: int = Field(ge=1, description="rubber_stamp: PRs with at least this many changed lines.")
    rubber_stamp_max_seconds: int = Field(ge=0, description="rubber_stamp: an approval faster than this is a stamp.")
    substantive_min_chars: int = Field(ge=0, description="Substantive: a line comment at least this long...")
    stock_phrases: list[str] = Field(description="...and not one of these phrases (case-insensitive). Sorted, unique.")
    escape_window_days: int = Field(ge=1, le=365, description="escape: a fix within this many days of merge.")
    stale_after_hours: int = Field(ge=1, description="stale_backlog: a review request unanswered for longer than this.")
    load_window_days: int = Field(ge=1, le=365, description="load_concentration: window in days.")
    load_top2_share: float = Field(gt=0, lt=1, description="load_concentration: top two reviewers above this share.")
    load_median_multiple: float = Field(ge=1, description="load_concentration: or anyone above this × median.")
    pattern_window_days: int = Field(ge=1, le=365, description="Repeat pattern: flags of one rule in this window...")
    pattern_min_count: int = Field(ge=2, description="...at least this many times.")
    self_approval_pattern_window_days: int = Field(ge=1, le=365, description="The same, for self-approvals.")
    self_approval_pattern_min_count: int = Field(ge=2)
    health_window_days: int = Field(ge=1, le=365, description="Health score: measured over this many days.")
    health_weight_coverage: float = Field(ge=0, le=1)
    health_weight_depth: float = Field(ge=0, le=1)
    health_weight_escapes: float = Field(ge=0, le=1)
    health_weight_responsiveness: float = Field(ge=0, le=1)
    health_weight_load_balance: float = Field(ge=0, le=1)
    health_escape_rate_floor: float = Field(gt=0, le=1, description="Health score: an escape rate this high scores 0.")

    @field_validator("stock_phrases")
    @classmethod
    def _normalize_phrases(cls, phrases: list[str]) -> list[str]:
        return sorted({p.strip().lower() for p in phrases if p.strip()})

    @model_validator(mode="after")
    def _weights_add_up(self) -> Self:
        total = (
            self.health_weight_coverage + self.health_weight_depth + self.health_weight_escapes
            + self.health_weight_responsiveness + self.health_weight_load_balance
        )
        if abs(total - 1) > 0.001:
            raise ValueError(f"the health score weights must add up to 100%, not {total:.0%}")
        return self


class SettingsOut(BaseModel):
    values: RuleSettings = Field(description="The settings in effect.")
    defaults: RuleSettings


class EngineRun(BaseModel):
    """What re-running the rules changed. Open flags that no longer fire are removed; triaged ones are kept."""

    created: int
    updated: int
    removed: int
    kept_triaged: int
    open_flags: int = Field(description="Open flags after the run.")


class SettingsSaved(SettingsOut):
    engine: EngineRun


class DemoReset(BaseModel):
    """The demo after a reset: rows loaded per table, and the flags with their starting triage."""

    rows: dict[str, int]
    flags: int
    open_flags: int


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
