"""Per-person profiles: flags split by role, active patterns, review debt and recent review activity.

Everything is read as of `now`, like the rules: requests answered or PRs merged after `now` are still pending.
"""

from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.models import Developer, Flag, FlagRole, FlagStatus, PullRequest, Review, ReviewRequest, RuleKey
from backend.rules.params import RuleParams
from backend.rules.patterns import active_patterns
from backend.rules.window_rules import ReviewLoad, review_load
from backend.schemas import (
    PatternOut,
    PendingReview,
    Person,
    PersonProfile,
    PullRequestRef,
    ReviewActivity,
    RoleSummary,
    RuleCount,
)


def _role_summary(flags: list[Flag], role: FlagRole) -> RoleSummary:
    mine = [f for f in flags if f.role == role and f.status != FlagStatus.dismissed]
    counts = Counter(f.rule_key for f in mine)
    return RoleSummary(
        flags=[RuleCount(rule_key=rule, count=counts[rule]) for rule in RuleKey if counts[rule]],
        open=sum(1 for f in mine if f.status == FlagStatus.open),
    )


def pending_requests(session: Session, now: datetime, reviewer_ids: Sequence[int] | None = None) -> list[ReviewRequest]:
    """Review requests still waiting at `now` (not answered, PR not merged), oldest first, with their PR loaded."""
    query = (
        select(ReviewRequest)
        .join(ReviewRequest.pull_request)
        .options(selectinload(ReviewRequest.pull_request))
        .where(
            ReviewRequest.requested_at <= now,
            or_(ReviewRequest.fulfilled_at.is_(None), ReviewRequest.fulfilled_at > now),
            or_(PullRequest.merged_at.is_(None), PullRequest.merged_at > now),
        )
        .order_by(ReviewRequest.requested_at, ReviewRequest.id)
    )
    if reviewer_ids is not None:
        query = query.where(ReviewRequest.reviewer_id.in_(reviewer_ids))
    return list(session.scalars(query))


def waiting_hours(request: ReviewRequest, now: datetime) -> float:
    return round((now - request.requested_at).total_seconds() / 3600, 1)


def current_load(session: Session, now: datetime, params: RuleParams) -> ReviewLoad:
    """The load rule's view of the team right now."""
    since = now - timedelta(days=params.load_window_days)
    reviews = session.scalars(select(Review).where(Review.submitted_at >= since, Review.submitted_at <= now)).all()
    return review_load(reviews, session.scalars(select(Developer)).all(), now, params)


def build_profiles(
    session: Session, people: Sequence[Developer], now: datetime, params: RuleParams
) -> list[PersonProfile]:
    """Profiles for `people`, in the given order. Queries once for everyone, not once per person."""
    ids = [p.id for p in people]

    flags = session.scalars(
        select(Flag).options(selectinload(Flag.pull_request)).where(Flag.person_id.in_(ids))
    ).all()
    flags_by_person: dict[int, list[Flag]] = {}
    for flag in flags:
        flags_by_person.setdefault(flag.person_id, []).append(flag)
    pr_refs = {f.pr_id: f.pull_request for f in flags if f.pull_request is not None}
    patterns = active_patterns(flags, now, params)

    pending = pending_requests(session, now, ids)
    load = current_load(session, now, params)
    since = now - timedelta(days=params.load_window_days)
    opened = dict(session.execute(
        select(PullRequest.author_id, func.count())
        .where(PullRequest.opened_at >= since, PullRequest.opened_at <= now)
        .group_by(PullRequest.author_id)
    ).all())

    stale_after = timedelta(hours=params.stale_after_hours)
    profiles = []
    for person in people:
        mine = flags_by_person.get(person.id, [])
        given = load.counts.get(person.id, 0)
        profiles.append(PersonProfile(
            person=Person.model_validate(person),
            as_author=_role_summary(mine, FlagRole.author),
            as_reviewer=_role_summary(mine, FlagRole.reviewer),
            patterns=[
                PatternOut(
                    rule_key=p.rule_key, role=p.role, count=p.count, window_days=p.window_days,
                    pull_requests=[PullRequestRef.model_validate(pr_refs[pr_id]) for pr_id in p.pr_ids],
                )
                for p in patterns
                if p.person_id == person.id
            ],
            review_debt=[
                PendingReview(
                    pull_request=PullRequestRef.model_validate(r.pull_request),
                    requested_at=r.requested_at,
                    waiting_hours=waiting_hours(r, now),
                    stale=now - r.requested_at > stale_after,
                )
                for r in pending
                if r.reviewer_id == person.id
            ],
            activity=ReviewActivity(
                window_days=params.load_window_days,
                reviews_given=given,
                team_reviews=load.total,
                share=round(given / load.total, 3) if load.total else 0.0,
                team_median=load.median,
                over_median_multiple=person.id in load.over_median_multiple,
                prs_opened=opened.get(person.id, 0),
            ),
        ))
    return profiles
