"""Ingested review data, shaped like data/seed.json (ids come from the source), plus the flags the
rule engine derives from it."""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


# SQLAlchemy stores enum member *names*; keeping names equal to values means the database
# holds the same strings as the data files ("manager", "changes_requested", ...).
class Role(enum.StrEnum):
    manager = "manager"
    dev = "dev"


class ReviewState(enum.StrEnum):
    approved = "approved"
    changes_requested = "changes_requested"
    commented = "commented"


class PullRequestKind(enum.StrEnum):
    normal = "normal"
    revert = "revert"
    hotfix = "hotfix"


class RuleKey(enum.StrEnum):
    merged_unreviewed = "merged_unreviewed"
    merged_changes_pending = "merged_changes_pending"
    self_approval = "self_approval"
    rubber_stamp = "rubber_stamp"
    escape = "escape"
    stale_backlog = "stale_backlog"
    load_concentration = "load_concentration"


class FlagRole(enum.StrEnum):
    """Which side of the review a flagged person was on."""

    author = "author"
    reviewer = "reviewer"


class FlagStatus(enum.StrEnum):
    open = "open"
    acknowledged = "acknowledged"
    dismissed = "dismissed"


class Developer(Base):
    __tablename__ = "developers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    handle: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[Role]


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        CheckConstraint("additions >= 0 AND deletions >= 0", name="ck_pull_requests_line_counts"),
        CheckConstraint("(merged_at IS NULL) = (merged_by_id IS NULL)", name="ck_pull_requests_merged_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    author_id: Mapped[int] = mapped_column(ForeignKey("developers.id"), index=True)
    merged_by_id: Mapped[int | None] = mapped_column(ForeignKey("developers.id"), index=True)
    opened_at: Mapped[datetime]
    merged_at: Mapped[datetime | None] = mapped_column(index=True)
    additions: Mapped[int]
    deletions: Mapped[int]
    fixes_pr_id: Mapped[int | None] = mapped_column(ForeignKey("pull_requests.id"), index=True)
    kind: Mapped[PullRequestKind] = mapped_column(default=PullRequestKind.normal)

    author: Mapped[Developer] = relationship(foreign_keys=[author_id])
    merged_by: Mapped[Developer | None] = relationship(foreign_keys=[merged_by_id])
    fixes: Mapped["PullRequest | None"] = relationship(remote_side=[id])
    reviews: Mapped[list["Review"]] = relationship(back_populates="pull_request", order_by="Review.submitted_at")
    review_requests: Mapped[list["ReviewRequest"]] = relationship(back_populates="pull_request")

    @property
    def lines_changed(self) -> int:
        return self.additions + self.deletions


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("developers.id"), index=True)
    state: Mapped[ReviewState]
    submitted_at: Mapped[datetime]

    pull_request: Mapped[PullRequest] = relationship(back_populates="reviews")
    reviewer: Mapped[Developer] = relationship()
    comments: Mapped[list["ReviewComment"]] = relationship(
        back_populates="review", order_by="ReviewComment.created_at"
    )


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    is_line_comment: Mapped[bool]
    created_at: Mapped[datetime]

    review: Mapped[Review] = relationship(back_populates="comments")


class ReviewRequest(Base):
    """Who was asked to review and when they responded. `fulfilled_at` is null while still waiting."""

    __tablename__ = "review_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("developers.id"), index=True)
    requested_at: Mapped[datetime]
    fulfilled_at: Mapped[datetime | None]

    pull_request: Mapped[PullRequest] = relationship(back_populates="review_requests")
    reviewer: Mapped[Developer] = relationship()


class Flag(Base):
    """A problem a rule found, plus its triage. Written by the rule engine; status and note by people.

    Identity across engine runs is (rule_key, pr_id, person_id, role). The unique constraint does not
    cover team-level flags (SQLite treats NULLs as distinct), so the engine keeps those unique itself.
    """

    __tablename__ = "flags"
    __table_args__ = (UniqueConstraint("rule_key", "pr_id", "person_id", "role", name="uq_flags_identity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_key: Mapped[RuleKey] = mapped_column(index=True)
    pr_id: Mapped[int | None] = mapped_column(ForeignKey("pull_requests.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("developers.id"), index=True)
    role: Mapped[FlagRole | None]
    occurred_at: Mapped[datetime]
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[FlagStatus] = mapped_column(default=FlagStatus.open, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    dismiss_reason: Mapped[str | None] = mapped_column(Text)

    pull_request: Mapped[PullRequest | None] = relationship()
    person: Mapped[Developer | None] = relationship()

    @property
    def key(self) -> tuple[RuleKey, int | None, int | None, FlagRole | None]:
        return (self.rule_key, self.pr_id, self.person_id, self.role)
