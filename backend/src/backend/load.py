"""Review load over time: who reviews how much, week by week and over the load rule's window."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Developer, Review, Role
from backend.profiles import pending_requests, waiting_hours
from backend.rules.params import RuleParams
from backend.rules.window_rules import review_load
from backend.schemas import LoadReport, LoadRow, Person

WEEK = timedelta(weeks=1)


def build_load_report(session: Session, now: datetime, params: RuleParams, weeks: int) -> LoadReport:
    """Weekly reviews for the last `weeks` weeks ending at `now`, plus the load rule's numbers right now."""
    developers = session.scalars(select(Developer)).all()
    devs = sorted((d for d in developers if d.role == Role.dev), key=lambda d: d.id)
    chart_start = now - weeks * WEEK
    earliest = min(chart_start, now - timedelta(days=params.load_window_days))
    reviews = session.scalars(select(Review).where(Review.submitted_at >= earliest, Review.submitted_at <= now)).all()

    load = review_load(reviews, developers, now, params)

    weekly = {d.id: [0] * weeks for d in devs}
    for review in reviews:
        if review.reviewer_id in weekly and review.submitted_at > chart_start:
            weeks_ago = int((now - review.submitted_at) // WEEK)
            weekly[review.reviewer_id][weeks - 1 - weeks_ago] += 1

    pending: dict[int, list] = {}
    for request in pending_requests(session, now, [d.id for d in devs]):
        pending.setdefault(request.reviewer_id, []).append(request)

    rows = []
    for dev in devs:
        reviews_in_window = load.counts[dev.id]
        waiting = pending.get(dev.id, [])
        rows.append(LoadRow(
            person=Person.model_validate(dev),
            weekly=weekly[dev.id],
            reviews=reviews_in_window,
            share=round(reviews_in_window / load.total, 3) if load.total else 0.0,
            median_multiple=round(reviews_in_window / load.median, 2) if load.median else None,
            over_median_multiple=dev.id in load.over_median_multiple,
            pending=len(waiting),
            oldest_pending_hours=waiting_hours(waiting[0], now) if waiting else None,
        ))
    rows.sort(key=lambda r: (-r.reviews, r.person.name))

    return LoadReport(
        as_of=now,
        week_starts=[chart_start + i * WEEK for i in range(weeks)],
        window_days=params.load_window_days,
        team_reviews=load.total,
        team_median=load.median,
        top2_share=round(load.top2_share, 3),
        top2_share_threshold=params.load_top2_share,
        median_multiple_threshold=params.load_median_multiple,
        concentrated=load.concentrated,
        people=rows,
    )
