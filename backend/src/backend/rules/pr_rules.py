"""Rules that look at one PR (and its reviews, comments and fix PRs) at a time.

Each rule takes every PR, with `reviews` and their `comments` loaded, and returns FlagCandidates.
None of them read the clock: their verdict on a PR does not change as time passes.
"""

from collections.abc import Callable, Sequence
from datetime import timedelta

from backend.models import FlagRole, PullRequest, Review, ReviewComment, ReviewState, RuleKey
from backend.rules.params import RuleParams
from backend.rules.types import FlagCandidate

PrRule = Callable[[Sequence[PullRequest], RuleParams], list[FlagCandidate]]


def is_substantive(comment: ReviewComment, params: RuleParams) -> bool:
    body = comment.body.strip()
    return (
        comment.is_line_comment
        and len(body) >= params.substantive_min_chars
        and body.lower().strip("!. ") not in params.stock_phrases
    )


def _reviews_in_order(pr: PullRequest) -> list[Review]:
    return sorted(pr.reviews, key=lambda r: r.submitted_at)


def _reviews_before_merge(pr: PullRequest) -> list[Review]:
    return [r for r in _reviews_in_order(pr) if r.submitted_at <= pr.merged_at]


def _approver_ids(pr: PullRequest) -> set[int]:
    return {r.reviewer_id for r in pr.reviews if r.state == ReviewState.approved}


def merged_unreviewed(prs: Sequence[PullRequest], params: RuleParams) -> list[FlagCandidate]:
    """Merged with no review submitted at or before the merge."""
    return [
        FlagCandidate(
            RuleKey.merged_unreviewed, pr.id, pr.author_id, FlagRole.author, pr.merged_at,
            {"lines": pr.lines_changed},
        )
        for pr in prs
        if pr.merged_at is not None and not _reviews_before_merge(pr)
    ]


def merged_changes_pending(prs: Sequence[PullRequest], params: RuleParams) -> list[FlagCandidate]:
    """Merged while some reviewer's latest verdict before the merge was changes_requested.

    A later `commented` review does not withdraw a change request; only approving does.
    """
    flags = []
    for pr in prs:
        if pr.merged_at is None:
            continue
        latest_verdict: dict[int, ReviewState] = {}
        for review in _reviews_before_merge(pr):
            if review.state != ReviewState.commented:
                latest_verdict[review.reviewer_id] = review.state
        pending = sorted(rid for rid, state in latest_verdict.items() if state == ReviewState.changes_requested)
        if pending:
            flags.append(FlagCandidate(
                RuleKey.merged_changes_pending, pr.id, pr.author_id, FlagRole.author, pr.merged_at,
                {"pending_reviewer_ids": pending},
            ))
    return flags


def self_approval(prs: Sequence[PullRequest], params: RuleParams) -> list[FlagCandidate]:
    """The author is the only person who approved."""
    return [
        FlagCandidate(RuleKey.self_approval, pr.id, pr.author_id, FlagRole.author, pr.merged_at or pr.opened_at)
        for pr in prs
        if _approver_ids(pr) == {pr.author_id}
    ]


def rubber_stamp(prs: Sequence[PullRequest], params: RuleParams) -> list[FlagCandidate]:
    """An approval on a big PR that came within seconds of opening or without one substantive comment.

    At most one flag per reviewer per PR: their first such approval.
    """
    flags = []
    for pr in prs:
        if pr.lines_changed < params.rubber_stamp_min_lines:
            continue
        flagged_reviewers: set[int] = set()
        for review in _reviews_in_order(pr):
            if review.state != ReviewState.approved or review.reviewer_id in flagged_reviewers:
                continue
            seconds = (review.submitted_at - pr.opened_at).total_seconds()
            substantive = sum(1 for c in review.comments if is_substantive(c, params))
            if seconds < params.rubber_stamp_max_seconds or substantive == 0:
                flagged_reviewers.add(review.reviewer_id)
                flags.append(FlagCandidate(
                    RuleKey.rubber_stamp, pr.id, review.reviewer_id, FlagRole.reviewer, review.submitted_at,
                    {"lines": pr.lines_changed, "seconds_to_approve": int(seconds), "substantive_comments": substantive},
                ))
    return flags


def escape(prs: Sequence[PullRequest], params: RuleParams) -> list[FlagCandidate]:
    """A revert or hotfix (a PR with `fixes_pr_id`) opened within the window after a merge.

    Flags every approver of the original PR, as reviewer; the author is not flagged. Uses the
    earliest qualifying fix if there are several.
    """
    fixes_by_pr: dict[int, list[PullRequest]] = {}
    for candidate in prs:
        if candidate.fixes_pr_id is not None:
            fixes_by_pr.setdefault(candidate.fixes_pr_id, []).append(candidate)

    window = timedelta(days=params.escape_window_days)
    flags = []
    for pr in prs:
        approvers = _approver_ids(pr)
        if pr.merged_at is None or not approvers:
            continue
        fix = next(
            (
                q for q in sorted(fixes_by_pr.get(pr.id, []), key=lambda q: q.opened_at)
                if timedelta(0) < q.opened_at - pr.merged_at <= window
            ),
            None,
        )
        if fix is None:
            continue
        for approver in sorted(approvers):
            flags.append(FlagCandidate(
                RuleKey.escape, pr.id, approver, FlagRole.reviewer, fix.opened_at,
                {"fix_pr_id": fix.id, "kind": fix.kind.value},
            ))
    return flags


PR_RULES: tuple[PrRule, ...] = (merged_unreviewed, merged_changes_pending, self_approval, rubber_stamp, escape)
