"""Rules whose verdict depends on "now": ages and rolling windows.

`now` is passed in (the engine uses `clock.now()`), and data is read as of `now`: anything that
happened after it is treated as not having happened yet.
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.models import Developer, FlagRole, Review, ReviewRequest, Role, RuleKey
from backend.rules.params import RuleParams
from backend.rules.types import FlagCandidate


def stale_backlog(requests: Sequence[ReviewRequest], now: datetime, params: RuleParams) -> list[FlagCandidate]:
    """A review request unanswered for longer than the threshold, on a PR that is not merged yet.

    Needs `request.pull_request` loaded. Flags the requested reviewer.
    """
    threshold = timedelta(hours=params.stale_after_hours)
    flags = []
    for request in requests:
        answered = request.fulfilled_at is not None and request.fulfilled_at <= now
        merged = request.pull_request.merged_at is not None and request.pull_request.merged_at <= now
        waited = now - request.requested_at
        if answered or merged or waited <= threshold:
            continue
        flags.append(FlagCandidate(
            RuleKey.stale_backlog, request.pr_id, request.reviewer_id, FlagRole.reviewer, request.requested_at,
            {"waiting_hours": round(waited.total_seconds() / 3600, 1)},
        ))
    return flags


@dataclass(frozen=True)
class ReviewLoad:
    """Review work per developer over the load window. Shared by the rule and every load figure the API shows."""

    counts: dict[int, int]  # developer id -> reviews in the window; manager excluded, developers with none are 0
    total: int
    top2_share: float  # share of `total` done by the two busiest developers; 0 when there are no reviews
    median: float
    over_median_multiple: list[int]  # developer ids above the median multiple, ascending
    concentrated: bool  # whether load_concentration fires


def review_load(
    reviews: Sequence[Review], developers: Sequence[Developer], now: datetime, params: RuleParams
) -> ReviewLoad:
    """Count reviews submitted in [now - window, now] per developer and apply the load thresholds."""
    since = now - timedelta(days=params.load_window_days)
    counts = {d.id: 0 for d in sorted(developers, key=lambda d: d.id) if d.role == Role.dev}
    for review in reviews:
        if review.reviewer_id in counts and since <= review.submitted_at <= now:
            counts[review.reviewer_id] += 1

    total = sum(counts.values())
    if total == 0:
        return ReviewLoad(counts, 0, 0.0, 0, [], False)
    top2_share = sum(sorted(counts.values(), reverse=True)[:2]) / total
    median = statistics.median(counts.values())
    heavy = sorted(d for d, n in counts.items() if median and n > params.load_median_multiple * median)
    concentrated = top2_share > params.load_top2_share or bool(heavy)
    return ReviewLoad(counts, total, top2_share, median, heavy, concentrated)


def load_concentration(
    reviews: Sequence[Review], developers: Sequence[Developer], now: datetime, params: RuleParams
) -> list[FlagCandidate]:
    """Team-level: review work over the window is concentrated on a few developers.

    Fires if the top two do more than the share threshold, or anyone exceeds the multiple of the median.
    """
    load = review_load(reviews, developers, now, params)
    if not load.concentrated:
        return []

    return [FlagCandidate(
        RuleKey.load_concentration, None, None, None, now,
        {
            "counts": {str(d): n for d, n in load.counts.items()},
            "top2_share": round(load.top2_share, 3),
            "median": load.median,
            "over_median_multiple": load.over_median_multiple,
            "window_days": params.load_window_days,
        },
    )]
