"""Edge cases for the per-PR rules, on small in-memory PRs (no database)."""

from datetime import datetime, timedelta, timezone

from backend.models import PullRequest, PullRequestKind, Review, ReviewComment, ReviewState
from backend.rules.params import DEFAULT_PARAMS, RuleParams
from backend.rules.pr_rules import (
    escape,
    escaping_fixes,
    is_rubber_stamp,
    is_substantive,
    merged_changes_pending,
    merged_unreviewed,
    rubber_stamp,
    self_approval,
)

T0 = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
AUTHOR, ALICE, BOB = 10, 11, 12
GOOD_COMMENT = "This drops the tenant id from the cache key."  # line comment, over 30 chars

APPROVED = ReviewState.approved
CHANGES = ReviewState.changes_requested
COMMENTED = ReviewState.commented


def comment(body: str = GOOD_COMMENT, line: bool = True) -> ReviewComment:
    return ReviewComment(body=body, is_line_comment=line, created_at=T0)


def review(reviewer: int, state: ReviewState, after: timedelta, comments: list[ReviewComment] = ()) -> Review:
    """A review submitted `after` the PR opened (all test PRs open at T0)."""
    return Review(reviewer_id=reviewer, state=state, submitted_at=T0 + after, comments=list(comments))


def pr(
    pr_id: int = 1,
    *,
    lines: int = 400,
    merged_after: timedelta | None = timedelta(hours=6),
    reviews: list[Review] = (),
    author: int = AUTHOR,
    opened: datetime = T0,
    fixes: int | None = None,
    kind: PullRequestKind = PullRequestKind.normal,
) -> PullRequest:
    return PullRequest(
        id=pr_id, title=f"PR {pr_id}", author_id=author, opened_at=opened,
        merged_at=None if merged_after is None else opened + merged_after,
        merged_by_id=None if merged_after is None else author,
        additions=lines, deletions=0, fixes_pr_id=fixes, kind=kind, reviews=list(reviews),
    )


def keys(flags) -> list[tuple]:
    return [(f.rule_key.value, f.pr_id, f.person_id, f.role.value) for f in flags]


H = timedelta(hours=1)
S = timedelta(seconds=1)


# ---------------------------------------------------------------- merged_unreviewed

def test_merged_with_no_reviews_is_flagged_with_line_count():
    [flag] = merged_unreviewed([pr(lines=37)], DEFAULT_PARAMS)
    assert keys([flag]) == [("merged_unreviewed", 1, AUTHOR, "author")]
    assert flag.evidence == {"lines": 37}
    assert flag.occurred_at == T0 + 6 * H


def test_review_only_after_merge_does_not_count():
    assert merged_unreviewed([pr(reviews=[review(ALICE, APPROVED, 7 * H)])], DEFAULT_PARAMS)


def test_review_exactly_at_merge_counts():
    assert not merged_unreviewed([pr(reviews=[review(ALICE, APPROVED, 6 * H)])], DEFAULT_PARAMS)


def test_open_pr_without_reviews_is_not_flagged():
    assert not merged_unreviewed([pr(merged_after=None)], DEFAULT_PARAMS)


# ---------------------------------------------------------------- merged_changes_pending

def test_changes_requested_then_approved_by_same_reviewer_is_fine():
    reviews = [review(ALICE, CHANGES, 1 * H), review(ALICE, APPROVED, 2 * H, [comment()])]
    assert not merged_changes_pending([pr(reviews=reviews)], DEFAULT_PARAMS)


def test_one_reviewer_still_requesting_changes_is_flagged():
    reviews = [review(ALICE, APPROVED, 1 * H, [comment()]), review(BOB, CHANGES, 2 * H)]
    [flag] = merged_changes_pending([pr(reviews=reviews)], DEFAULT_PARAMS)
    assert keys([flag]) == [("merged_changes_pending", 1, AUTHOR, "author")]
    assert flag.evidence == {"pending_reviewer_ids": [BOB]}


def test_a_later_comment_does_not_withdraw_a_change_request():
    reviews = [review(BOB, CHANGES, 1 * H), review(BOB, COMMENTED, 2 * H)]
    assert merged_changes_pending([pr(reviews=reviews)], DEFAULT_PARAMS)


def test_change_request_after_merge_is_ignored():
    reviews = [review(ALICE, APPROVED, 1 * H, [comment()]), review(BOB, CHANGES, 7 * H)]
    assert not merged_changes_pending([pr(reviews=reviews)], DEFAULT_PARAMS)


# ---------------------------------------------------------------- self_approval

def test_author_as_only_approver_is_flagged_at_merge_time():
    [flag] = self_approval([pr(reviews=[review(AUTHOR, APPROVED, 1 * H)])], DEFAULT_PARAMS)
    assert keys([flag]) == [("self_approval", 1, AUTHOR, "author")]
    assert flag.occurred_at == T0 + 6 * H


def test_self_approval_on_open_pr_uses_opened_time():
    [flag] = self_approval([pr(merged_after=None, reviews=[review(AUTHOR, APPROVED, 1 * H)])], DEFAULT_PARAMS)
    assert flag.occurred_at == T0


def test_author_plus_another_approver_is_fine():
    reviews = [review(AUTHOR, APPROVED, 1 * H), review(ALICE, APPROVED, 2 * H, [comment()])]
    assert not self_approval([pr(reviews=reviews)], DEFAULT_PARAMS)


def test_no_approvals_is_not_self_approval():
    assert not self_approval([pr(reviews=[review(ALICE, CHANGES, 1 * H)])], DEFAULT_PARAMS)


# ---------------------------------------------------------------- substantive comments

def test_substantive_needs_a_line_comment_of_minimum_length():
    assert is_substantive(comment("x" * 30), DEFAULT_PARAMS)
    assert not is_substantive(comment("x" * 29), DEFAULT_PARAMS)
    assert not is_substantive(comment(GOOD_COMMENT, line=False), DEFAULT_PARAMS)


def test_stock_phrases_are_never_substantive():
    no_length_limit = RuleParams(substantive_min_chars=0)
    assert not is_substantive(comment("LGTM!"), no_length_limit)
    assert not is_substantive(comment("  Ship it. "), no_length_limit)
    assert is_substantive(comment("Rename this"), no_length_limit)


# ---------------------------------------------------------------- rubber_stamp

def test_fast_approval_on_big_pr_is_flagged_even_with_comments():
    [flag] = rubber_stamp([pr(lines=300, reviews=[review(ALICE, APPROVED, 119 * S, [comment()])])], DEFAULT_PARAMS)
    assert keys([flag]) == [("rubber_stamp", 1, ALICE, "reviewer")]
    assert flag.evidence == {"lines": 300, "seconds_to_approve": 119, "substantive_comments": 1}


def test_small_pr_is_never_a_rubber_stamp():
    assert not rubber_stamp([pr(lines=299, reviews=[review(ALICE, APPROVED, 5 * S)])], DEFAULT_PARAMS)


def test_approval_at_threshold_with_substantive_comment_is_fine():
    assert not rubber_stamp([pr(reviews=[review(ALICE, APPROVED, 120 * S, [comment()])])], DEFAULT_PARAMS)


def test_slow_approval_without_substantive_comment_is_flagged():
    reviews = [review(ALICE, APPROVED, 3 * H, [comment("LGTM"), comment(GOOD_COMMENT, line=False)])]
    [flag] = rubber_stamp([pr(reviews=reviews)], DEFAULT_PARAMS)
    assert flag.evidence["substantive_comments"] == 0
    assert flag.evidence["seconds_to_approve"] == 3 * 3600


def test_only_approvals_can_be_rubber_stamps():
    assert not rubber_stamp([pr(reviews=[review(ALICE, CHANGES, 10 * S)])], DEFAULT_PARAMS)


def test_one_flag_per_reviewer_per_pr():
    reviews = [review(ALICE, APPROVED, 10 * S), review(ALICE, APPROVED, 20 * S), review(BOB, APPROVED, 30 * S)]
    flags = rubber_stamp([pr(reviews=reviews)], DEFAULT_PARAMS)
    assert keys(flags) == [("rubber_stamp", 1, ALICE, "reviewer"), ("rubber_stamp", 1, BOB, "reviewer")]
    assert flags[0].evidence["seconds_to_approve"] == 10


# ---------------------------------------------------------------- escape

def _original(reviews: list[Review]) -> PullRequest:
    return pr(1, reviews=reviews)


def _fix(opened: datetime, pr_id: int = 2, kind: PullRequestKind = PullRequestKind.hotfix) -> PullRequest:
    return pr(pr_id, lines=20, opened=opened, fixes=1, kind=kind)


MERGED_AT = T0 + 6 * H


def test_fix_within_window_flags_every_approver():
    original = _original([review(BOB, APPROVED, 1 * H, [comment()]), review(ALICE, APPROVED, 2 * H, [comment()])])
    flags = escape([original, _fix(MERGED_AT + timedelta(days=14), kind=PullRequestKind.revert)], DEFAULT_PARAMS)
    assert keys(flags) == [("escape", 1, ALICE, "reviewer"), ("escape", 1, BOB, "reviewer")]
    assert flags[0].evidence == {"fix_pr_id": 2, "kind": "revert"}
    assert flags[0].occurred_at == MERGED_AT + timedelta(days=14)


def test_fix_after_window_is_not_an_escape():
    original = _original([review(ALICE, APPROVED, 1 * H, [comment()])])
    assert not escape([original, _fix(MERGED_AT + timedelta(days=14) + S)], DEFAULT_PARAMS)


def test_fix_opened_before_merge_is_not_an_escape():
    original = _original([review(ALICE, APPROVED, 1 * H, [comment()])])
    assert not escape([original, _fix(MERGED_AT - H)], DEFAULT_PARAMS)


def test_unreviewed_pr_with_fix_has_no_one_to_flag():
    assert not escape([_original([]), _fix(MERGED_AT + H)], DEFAULT_PARAMS)


def test_earliest_fix_is_used():
    original = _original([review(ALICE, APPROVED, 1 * H, [comment()])])
    fixes = [_fix(MERGED_AT + 3 * H, pr_id=3), _fix(MERGED_AT + 2 * H, pr_id=2)]
    [flag] = escape([original, *fixes], DEFAULT_PARAMS)
    assert flag.evidence["fix_pr_id"] == 2


def test_escaping_fixes_maps_the_original_to_its_earliest_fix_even_when_unreviewed():
    fixes = [_fix(MERGED_AT + 3 * H, pr_id=3), _fix(MERGED_AT + 2 * H, pr_id=2)]
    assert {pr_id: fix.id for pr_id, fix in escaping_fixes([_original([]), *fixes], DEFAULT_PARAMS).items()} == {1: 2}


# ---------------------------------------------------------------- is_rubber_stamp (shared with the quality report)

def test_is_rubber_stamp_matches_the_rule():
    big = pr(lines=400)
    assert is_rubber_stamp(big, review(ALICE, APPROVED, 60 * S, [comment()]), DEFAULT_PARAMS)  # too fast
    assert is_rubber_stamp(big, review(ALICE, APPROVED, 2 * H), DEFAULT_PARAMS)  # no substantive comment
    assert not is_rubber_stamp(big, review(ALICE, APPROVED, 2 * H, [comment()]), DEFAULT_PARAMS)
    assert not is_rubber_stamp(big, review(ALICE, COMMENTED, 60 * S), DEFAULT_PARAMS)
    assert not is_rubber_stamp(pr(lines=299), review(ALICE, APPROVED, 60 * S), DEFAULT_PARAMS)
