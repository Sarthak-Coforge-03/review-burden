"""Review quality per reviewer: how fast they approve, how much they say, and how often approved work came back.

Reviews submitted in (now - weeks, now] count. Rubber stamps and escapes use the rules' own tests,
so these numbers agree with the flags.
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models import Developer, PullRequest, Review, ReviewState, Role
from backend.rules.params import RuleParams
from backend.rules.pr_rules import escaping_fixes, is_rubber_stamp, is_substantive
from backend.schemas import Person, QualityMedians, QualityReport, QualityRow


@dataclass
class _Tally:
    reviews: int = 0
    approvals: int = 0
    lines_reviewed: int = 0
    comments: int = 0
    substantive: int = 0
    big_approvals: int = 0
    stamped_big_approvals: int = 0
    approved_merged: int = 0
    escapes: int = 0
    minutes_per_100: list[float] = field(default_factory=list)


def _ratio(part: float, whole: float, digits: int = 3) -> float | None:
    return round(part / whole, digits) if whole else None


def _median(values: list[float | None], digits: int = 3) -> float | None:
    present = [v for v in values if v is not None]
    return round(statistics.median(present), digits) if present else None


def build_quality_report(session: Session, now: datetime, params: RuleParams, weeks: int) -> QualityReport:
    since = now - timedelta(weeks=weeks)
    devs = session.scalars(select(Developer).where(Developer.role == Role.dev).order_by(Developer.name)).all()
    prs = session.scalars(
        select(PullRequest).options(selectinload(PullRequest.reviews).selectinload(Review.comments))
    ).all()
    fixes = {pr_id: fix for pr_id, fix in escaping_fixes(prs, params).items() if fix.opened_at <= now}

    tallies = {d.id: _Tally() for d in devs}
    for pr in prs:
        by_reviewer: dict[int, list[Review]] = {}
        for review in sorted(pr.reviews, key=lambda r: r.submitted_at):
            if review.reviewer_id in tallies and since < review.submitted_at <= now:
                by_reviewer.setdefault(review.reviewer_id, []).append(review)

        for reviewer_id, reviews in by_reviewer.items():
            t = tallies[reviewer_id]
            t.reviews += len(reviews)
            t.lines_reviewed += pr.lines_changed
            comments = [c for r in reviews for c in r.comments]
            t.comments += len(comments)
            t.substantive += sum(1 for c in comments if is_substantive(c, params))

            approvals = [r for r in reviews if r.state == ReviewState.approved]
            if not approvals:
                continue
            t.approvals += 1
            if pr.lines_changed:
                minutes = (approvals[0].submitted_at - pr.opened_at).total_seconds() / 60
                t.minutes_per_100.append(minutes / (pr.lines_changed / 100))
            if pr.lines_changed >= params.rubber_stamp_min_lines:
                t.big_approvals += 1
                t.stamped_big_approvals += any(is_rubber_stamp(pr, r, params) for r in approvals)
            if pr.merged_at is not None and pr.merged_at <= now:
                t.approved_merged += 1
                t.escapes += pr.id in fixes

    rows = []
    for dev in devs:
        t = tallies[dev.id]
        rows.append(QualityRow(
            person=Person.model_validate(dev),
            reviews=t.reviews,
            approvals=t.approvals,
            minutes_per_100_lines=_median(t.minutes_per_100, 1),
            comments=t.comments,
            comments_per_100_lines=_ratio(t.comments * 100, t.lines_reviewed, 2),
            substantive_share=_ratio(t.substantive, t.comments),
            big_approvals=t.big_approvals,
            stamped_big_approvals=t.stamped_big_approvals,
            approved_merged=t.approved_merged,
            escapes=t.escapes,
            escape_rate=_ratio(t.escapes, t.approved_merged),
        ))

    return QualityReport(
        as_of=now,
        since=since,
        weeks=weeks,
        big_pr_lines=params.rubber_stamp_min_lines,
        escape_window_days=params.escape_window_days,
        medians=QualityMedians(
            minutes_per_100_lines=_median([r.minutes_per_100_lines for r in rows], 1),
            comments_per_100_lines=_median([r.comments_per_100_lines for r in rows], 2),
            substantive_share=_median([r.substantive_share for r in rows]),
            escape_rate=_median([r.escape_rate for r in rows]),
        ),
        people=rows,
    )
