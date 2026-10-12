"""Edge cases for the rules that depend on "now", on small in-memory data (no database)."""

from datetime import datetime, timedelta, timezone

from backend.models import Developer, PullRequest, Review, ReviewRequest, ReviewState, Role
from backend.rules.params import DEFAULT_PARAMS
from backend.rules.window_rules import load_concentration, stale_backlog

NOW = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)
H = timedelta(hours=1)
D = timedelta(days=1)
S = timedelta(seconds=1)
MANAGER, ARJUN = 1, 2


# ---------------------------------------------------------------- stale_backlog

def request(
    waited: timedelta, *, fulfilled_after: timedelta | None = None, merged_after: timedelta | None = None
) -> ReviewRequest:
    """A request made `waited` before NOW; fulfilment and merge are offsets from the request."""
    requested_at = NOW - waited
    pr = PullRequest(
        id=7, title="PR 7", author_id=3, opened_at=requested_at, additions=10, deletions=0,
        merged_at=None if merged_after is None else requested_at + merged_after,
        merged_by_id=None if merged_after is None else 3,
    )
    return ReviewRequest(
        pr_id=7, reviewer_id=ARJUN, requested_at=requested_at, pull_request=pr,
        fulfilled_at=None if fulfilled_after is None else requested_at + fulfilled_after,
    )


def test_request_waiting_past_threshold_is_flagged():
    [flag] = stale_backlog([request(75.9 * H)], NOW, DEFAULT_PARAMS)
    assert (flag.rule_key, flag.pr_id, flag.person_id, flag.role) == ("stale_backlog", 7, ARJUN, "reviewer")
    assert flag.evidence == {"waiting_hours": 75.9}
    assert flag.occurred_at == NOW - 75.9 * H


def test_exactly_at_threshold_is_not_stale_yet():
    assert not stale_backlog([request(48 * H)], NOW, DEFAULT_PARAMS)
    assert stale_backlog([request(48 * H + S)], NOW, DEFAULT_PARAMS)


def test_answered_request_is_not_stale():
    assert not stale_backlog([request(100 * H, fulfilled_after=60 * H)], NOW, DEFAULT_PARAMS)


def test_answer_after_now_has_not_happened_yet():
    assert stale_backlog([request(100 * H, fulfilled_after=101 * H)], NOW, DEFAULT_PARAMS)


def test_request_on_merged_pr_is_not_waiting_on_anyone():
    assert not stale_backlog([request(100 * H, merged_after=10 * H)], NOW, DEFAULT_PARAMS)
    assert stale_backlog([request(100 * H, merged_after=101 * H)], NOW, DEFAULT_PARAMS)


# ---------------------------------------------------------------- load_concentration

def team(dev_count: int) -> list[Developer]:
    devs = [Developer(id=MANAGER, name="M", handle="m", role=Role.manager)]
    return devs + [Developer(id=i, name=f"D{i}", handle=f"d{i}", role=Role.dev) for i in range(2, 2 + dev_count)]


def reviews_by(counts: dict[int, int], ago: timedelta = D) -> list[Review]:
    return [
        Review(reviewer_id=who, state=ReviewState.approved, submitted_at=NOW - ago)
        for who, n in counts.items()
        for _ in range(n)
    ]


def test_balanced_team_is_not_flagged():
    assert not load_concentration(reviews_by({2: 5, 3: 5, 4: 4, 5: 5}), team(4), NOW, DEFAULT_PARAMS)


def test_one_reviewer_over_twice_the_median_is_flagged():
    [flag] = load_concentration(reviews_by({2: 20, 3: 5, 4: 4, 5: 5, 6: 6}), team(5), NOW, DEFAULT_PARAMS)
    assert (flag.rule_key, flag.pr_id, flag.person_id, flag.role) == ("load_concentration", None, None, None)
    assert flag.occurred_at == NOW
    assert flag.evidence == {
        "counts": {"2": 20, "3": 5, "4": 4, "5": 5, "6": 6},
        "top2_share": 0.65,
        "median": 5,
        "over_median_multiple": [2],
        "window_days": 28,
    }


def test_top_two_share_alone_is_enough():
    [flag] = load_concentration(reviews_by({2: 5, 3: 5, 4: 2, 5: 1}), team(4), NOW, DEFAULT_PARAMS)
    assert flag.evidence["over_median_multiple"] == []
    assert flag.evidence["top2_share"] == 0.769


def test_top_two_share_at_threshold_is_not_flagged():
    assert not load_concentration(reviews_by({2: 3, 3: 3, 4: 2, 5: 2}), team(4), NOW, DEFAULT_PARAMS)


def test_developers_without_reviews_count_toward_the_median():
    [flag] = load_concentration(reviews_by({2: 3, 3: 1}), team(4), NOW, DEFAULT_PARAMS)
    assert flag.evidence["counts"] == {"2": 3, "3": 1, "4": 0, "5": 0}
    assert flag.evidence["median"] == 0.5


def test_manager_and_out_of_window_reviews_are_ignored():
    in_window = reviews_by({2: 5, 3: 5, 4: 5, 5: 5})
    ignored = (
        reviews_by({MANAGER: 50})
        + reviews_by({2: 50}, ago=28 * D + S)
        + reviews_by({2: 50}, ago=-S)
    )
    assert not load_concentration(in_window + ignored, team(4), NOW, DEFAULT_PARAMS)


def test_no_reviews_is_not_flagged():
    assert not load_concentration([], team(4), NOW, DEFAULT_PARAMS)
