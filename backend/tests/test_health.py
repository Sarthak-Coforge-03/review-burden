"""Health score parts on small in-memory PRs (no database)."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from backend.health import health_parts, health_score
from backend.models import Developer, PullRequest, Review, ReviewComment, ReviewRequest, ReviewState, Role
from backend.rules.params import DEFAULT_PARAMS
from backend.schemas import HealthPart, HealthPartKey

AT = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
H = timedelta(hours=1)
D = timedelta(days=1)
AUTHOR, ALICE, BOB, CAROL = 10, 11, 12, 13
DEVS = [Developer(id=i, name=str(i), handle=str(i), role=Role.dev) for i in (AUTHOR, ALICE, BOB, CAROL)]
GOOD_COMMENT = "This drops the tenant id from the cache key."


def review(reviewer: int, opened: datetime, after: timedelta, state=ReviewState.approved, comment=True) -> Review:
    comments = [ReviewComment(body=GOOD_COMMENT, is_line_comment=True, created_at=opened + after)] if comment else []
    return Review(reviewer_id=reviewer, state=state, submitted_at=opened + after, comments=comments)


def pr(
    pr_id: int,
    opened: datetime,
    *,
    lines: int = 100,
    merged_after: timedelta | None = 6 * H,
    approvers: tuple[int, ...] = (ALICE,),
    requests: list[ReviewRequest] = (),
    fixes: int | None = None,
) -> PullRequest:
    return PullRequest(
        id=pr_id, title=str(pr_id), author_id=AUTHOR, opened_at=opened,
        merged_at=None if merged_after is None else opened + merged_after,
        merged_by_id=None if merged_after is None else AUTHOR,
        additions=lines, deletions=0, fixes_pr_id=fixes,
        reviews=[review(a, opened, 2 * H) for a in approvers], review_requests=list(requests),
    )


def parts(prs, params=DEFAULT_PARAMS) -> dict[HealthPartKey, HealthPart]:
    return {p.key: p for p in health_parts(prs, DEVS, AT, params)}


def test_coverage_needs_an_approval_from_someone_else_before_merge():
    late = pr(3, AT - 5 * D, approvers=())
    late.reviews.append(review(ALICE, late.opened_at, 7 * H))  # after the 6h merge
    prs = [pr(1, AT - 5 * D), pr(2, AT - 5 * D, approvers=(AUTHOR,)), late, pr(4, AT - 40 * D)]  # 4 is outside
    coverage = parts(prs)[HealthPartKey.coverage]
    assert (coverage.good, coverage.total, coverage.score) == (1, 3, 33)


def test_depth_counts_rubber_stamps_on_big_prs():
    stamped = pr(1, AT - 5 * D, lines=400, approvers=())
    stamped.reviews.append(review(ALICE, stamped.opened_at, 60 * timedelta(seconds=1)))  # approved in a minute
    prs = [stamped, pr(2, AT - 5 * D, lines=400, approvers=(ALICE, BOB)), pr(3, AT - 5 * D, lines=50)]
    depth = parts(prs)[HealthPartKey.depth]
    assert (depth.good, depth.total, depth.score) == (2, 3, 67)


def test_escape_score_falls_to_zero_at_the_floor():
    prs = [pr(i, AT - 10 * D) for i in range(1, 21)]
    prs.append(pr(99, AT - 9 * D, fixes=1))  # 1 of 21 approved PRs escaped: 4.8%, half the 10% floor
    escapes = parts(prs)[HealthPartKey.escapes]
    assert (escapes.good, escapes.total, escapes.score) == (20, 21, 52)
    prs.append(pr(98, AT - 9 * D, fixes=2))  # 2 of 22: 9.1%, just under the floor
    assert parts(prs)[HealthPartKey.escapes].score == 9
    prs.append(pr(97, AT - 9 * D, fixes=3))  # 3 of 23: 13%, past the floor
    assert parts(prs)[HealthPartKey.escapes].score == 0


def test_fix_opened_after_at_is_not_counted_yet():
    prs = [pr(1, AT - 3 * D), pr(2, AT + H, fixes=1, merged_after=None)]
    assert parts(prs)[HealthPartKey.escapes].score == 100


def test_responsiveness_ignores_requests_still_inside_the_threshold():
    def request(requested: datetime, answered_after: timedelta | None) -> ReviewRequest:
        fulfilled = None if answered_after is None else requested + answered_after
        return ReviewRequest(reviewer_id=ALICE, requested_at=requested, fulfilled_at=fulfilled)

    open_pr = pr(1, AT - 10 * D, merged_after=None, requests=[
        request(AT - 10 * D, 3 * H),  # answered in time
        request(AT - 10 * D, 72 * H),  # answered late
        request(AT - 5 * D, None),  # still waiting, past the threshold
        request(AT - 10 * H, None),  # still waiting, not stale yet: not counted
    ])
    merged_quickly = pr(2, AT - 3 * D, requests=[request(AT - 3 * D, None)])  # merged before an answer
    responsiveness = parts([open_pr, merged_quickly])[HealthPartKey.responsiveness]
    assert (responsiveness.good, responsiveness.total, responsiveness.score) == (2, 4, 50)


def test_load_balance_is_full_until_the_top_two_pass_the_threshold():
    def reviewed_by(*reviewers: int) -> list[PullRequest]:
        return [pr(i, AT - 5 * D, approvers=(r,)) for i, r in enumerate(reviewers, start=1)]

    concentrated = parts(reviewed_by(ALICE, BOB, CAROL, ALICE, BOB))[HealthPartKey.load_balance]  # top two: 80%
    assert (concentrated.good, concentrated.total, concentrated.score) == (1, 5, 50)
    at_threshold = parts(reviewed_by(ALICE, BOB, CAROL, AUTHOR, ALICE))[HealthPartKey.load_balance]  # top two: 60%
    assert at_threshold.score == 100


def test_score_reweights_around_parts_with_nothing_to_measure():
    def part(key, weight, score):
        return HealthPart(key=key, weight=weight, good=0, total=0, score=score)

    assert health_score([part(HealthPartKey.coverage, 0.25, 80), part(HealthPartKey.depth, 0.25, None),
                         part(HealthPartKey.escapes, 0.5, 50)]) == 60
    assert health_score([part(HealthPartKey.depth, 0.25, None)]) is None


def test_empty_window_has_no_score():
    old = [pr(1, AT - 60 * D)]
    assert all(p.score is None for p in health_parts(old, DEVS, AT, DEFAULT_PARAMS))
    assert health_score(health_parts(old, DEVS, AT, DEFAULT_PARAMS)) is None


def test_weights_come_from_params():
    params = replace(DEFAULT_PARAMS, health_weight_coverage=0.5)
    assert parts([pr(1, AT - D)], params)[HealthPartKey.coverage].weight == 0.5
