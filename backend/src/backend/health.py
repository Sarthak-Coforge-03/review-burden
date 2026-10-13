"""Team health score: five parts, each 0-100, weighted together.

Every part is read as of a moment `at`, over the window before it, using the same checks as the flags:
coverage (merged PRs approved by someone else), depth (big-PR approvals that are not rubber stamps),
escapes (approved PRs that did not need a revert or hotfix), responsiveness (review requests answered
within the stale threshold) and load balance (how much the two busiest reviewers carry). Load balance
uses the load rule's own window. A part with nothing to measure is left out and the others share its weight.
"""

import statistics
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.models import Developer, Flag, FlagStatus, PullRequest, Review, ReviewState
from backend.profiles import pending_requests
from backend.rules.params import RuleParams
from backend.rules.pr_rules import escaping_fixes, is_rubber_stamp
from backend.rules.window_rules import review_load
from backend.schemas import HealthPart, HealthPartKey, HealthSnapshot, Overview, OverviewKpis

WEEK = timedelta(weeks=1)


def _in(moment: datetime | None, since: datetime, until: datetime) -> bool:
    return moment is not None and since < moment <= until


def _share_score(good: int, total: int) -> int | None:
    return round(100 * good / total) if total else None


def _approved_by_other(pr: PullRequest) -> bool:
    return any(
        r.state == ReviewState.approved and r.reviewer_id != pr.author_id and r.submitted_at <= pr.merged_at
        for r in pr.reviews
    )


def health_parts(
    prs: Sequence[PullRequest], developers: Sequence[Developer], at: datetime, params: RuleParams
) -> list[HealthPart]:
    """The five parts as of `at`. `prs` are every PR, with reviews, their comments and review requests loaded."""
    since = at - timedelta(days=params.health_window_days)
    merged = [pr for pr in prs if _in(pr.merged_at, since, at)]

    covered = [pr for pr in merged if _approved_by_other(pr)]

    big_approvals = stamped = 0
    for pr in prs:
        if pr.lines_changed < params.rubber_stamp_min_lines:
            continue
        approvals: dict[int, list[Review]] = {}
        for r in pr.reviews:
            if r.state == ReviewState.approved and _in(r.submitted_at, since, at):
                approvals.setdefault(r.reviewer_id, []).append(r)
        big_approvals += len(approvals)
        stamped += sum(any(is_rubber_stamp(pr, r, params) for r in rs) for rs in approvals.values())
    unstamped = big_approvals - stamped

    fixes = escaping_fixes(prs, params)
    escaped = sum(1 for pr in covered if pr.id in fixes and fixes[pr.id].opened_at <= at)
    escape_score = None
    if covered:
        escape_score = round(100 * max(0.0, 1 - escaped / len(covered) / params.health_escape_rate_floor))

    on_time = decided = 0
    stale_after = timedelta(hours=params.stale_after_hours)
    for pr in prs:
        for request in pr.review_requests:
            if not _in(request.requested_at, since, at):
                continue
            deadline = request.requested_at + stale_after
            responses = [m for m in (request.fulfilled_at, pr.merged_at) if m is not None and m <= at]
            if responses and min(responses) <= deadline:
                on_time += 1
                decided += 1
            elif at > deadline:
                decided += 1

    load = review_load([r for pr in prs for r in pr.reviews], developers, at, params)
    top2 = sum(sorted(load.counted.values(), reverse=True)[:2])
    if not load.total:
        balance = None
    elif load.top2_share <= params.load_top2_share:
        balance = 100
    else:
        balance = round(100 * (1 - load.top2_share) / (1 - params.load_top2_share))

    return [
        HealthPart(
            key=HealthPartKey.coverage, weight=params.health_weight_coverage,
            good=len(covered), total=len(merged), score=_share_score(len(covered), len(merged)),
        ),
        HealthPart(
            key=HealthPartKey.depth, weight=params.health_weight_depth,
            good=unstamped, total=big_approvals, score=_share_score(unstamped, big_approvals),
        ),
        HealthPart(
            key=HealthPartKey.escapes, weight=params.health_weight_escapes,
            good=len(covered) - escaped, total=len(covered), score=escape_score,
        ),
        HealthPart(
            key=HealthPartKey.responsiveness, weight=params.health_weight_responsiveness,
            good=on_time, total=decided, score=_share_score(on_time, decided),
        ),
        HealthPart(
            key=HealthPartKey.load_balance, weight=params.health_weight_load_balance,
            good=load.total - top2, total=load.total, score=balance,
        ),
    ]


def health_score(parts: Sequence[HealthPart]) -> int | None:
    measured = [p for p in parts if p.score is not None and p.weight > 0]
    weight = sum(p.weight for p in measured)
    return round(sum(p.weight * p.score for p in measured) / weight) if weight else None


def _hours_to_first_review(prs: Sequence[PullRequest], since: datetime, at: datetime) -> float | None:
    hours = []
    for pr in prs:
        if not _in(pr.opened_at, since, at):
            continue
        reviewed = [r.submitted_at for r in pr.reviews if r.reviewer_id != pr.author_id and r.submitted_at <= at]
        if reviewed:
            first = min(reviewed)
            hours.append((first - pr.opened_at).total_seconds() / 3600)
    return round(statistics.median(hours), 1) if hours else None


def build_overview(session: Session, now: datetime, params: RuleParams, weeks: int) -> Overview:
    """The score and its parts now, the KPI tiles, and the score at the end of each of the last `weeks` weeks."""
    prs = session.scalars(
        select(PullRequest).options(
            selectinload(PullRequest.reviews).selectinload(Review.comments),
            selectinload(PullRequest.review_requests),
        )
    ).all()
    developers = session.scalars(select(Developer)).all()
    since = now - timedelta(days=params.health_window_days)

    parts = health_parts(prs, developers, now, params)
    first_pr = min((pr.opened_at for pr in prs), default=now)
    window = timedelta(days=params.health_window_days)
    trend = []
    for weeks_ago in range(weeks - 1, 0, -1):
        at = now - weeks_ago * WEEK
        if at - window >= first_pr:
            trend.append(HealthSnapshot(as_of=at, score=health_score(health_parts(prs, developers, at, params))))
    trend.append(HealthSnapshot(as_of=now, score=health_score(parts)))

    waiting = pending_requests(session, now)
    stale_after = timedelta(hours=params.stale_after_hours)
    open_flags = session.scalar(select(func.count()).select_from(Flag).where(Flag.status == FlagStatus.open))

    return Overview(
        as_of=now,
        since=since,
        window_days=params.health_window_days,
        escape_rate_floor=params.health_escape_rate_floor,
        top2_share_threshold=params.load_top2_share,
        dedicated_reviewers=len(params.load_dedicated_reviewers),
        stale_after_hours=params.stale_after_hours,
        score=health_score(parts),
        parts=parts,
        kpis=OverviewKpis(
            open_flags=open_flags,
            prs_merged=sum(1 for pr in prs if _in(pr.merged_at, since, now)),
            median_hours_to_first_review=_hours_to_first_review(prs, since, now),
            waiting_reviews=len(waiting),
            stale_reviews=sum(1 for r in waiting if now - r.requested_at > stale_after),
        ),
        trend=trend,
    )
