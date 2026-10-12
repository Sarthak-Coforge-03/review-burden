"""Load the data, run every rule, and reconcile the results with the stored flags."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend import clock
from backend.models import Developer, Flag, FlagStatus, PullRequest, Review, ReviewRequest
from backend.rules.params import DEFAULT_PARAMS, RuleParams
from backend.rules.pr_rules import PR_RULES
from backend.rules.types import FlagCandidate
from backend.rules.window_rules import load_concentration, stale_backlog


@dataclass(frozen=True)
class EngineResult:
    created: int
    updated: int
    removed: int
    kept_triaged: int  # triaged flags whose rule no longer fires; kept so their note is not lost


def evaluate(session: Session, now: datetime, params: RuleParams) -> list[FlagCandidate]:
    """Every flag the rules find right now. Reads only; stores nothing."""
    prs = session.scalars(
        select(PullRequest).options(selectinload(PullRequest.reviews).selectinload(Review.comments))
    ).all()
    requests = session.scalars(select(ReviewRequest).options(selectinload(ReviewRequest.pull_request))).all()
    developers = session.scalars(select(Developer)).all()
    reviews = [review for pr in prs for review in pr.reviews]

    candidates = [flag for rule in PR_RULES for flag in rule(prs, params)]
    candidates += stale_backlog(requests, now, params)
    candidates += load_concentration(reviews, developers, now, params)
    return candidates


def run_engine(session: Session, now: datetime | None = None, params: RuleParams = DEFAULT_PARAMS) -> EngineResult:
    """Bring the flags table in line with what the rules find. Flushes; the caller commits.

    - New problems become open flags.
    - Flags that still fire get fresh evidence and occurred_at; status, note and dismiss reason are kept.
    - Flags that no longer fire are deleted if open, and kept untouched if acknowledged or dismissed.
    """
    candidates = evaluate(session, now or clock.now(), params)
    stored = {flag.key: flag for flag in session.scalars(select(Flag))}

    created = updated = 0
    for candidate in candidates:
        flag = stored.pop(candidate.key, None)
        if flag is None:
            session.add(Flag(
                rule_key=candidate.rule_key, pr_id=candidate.pr_id, person_id=candidate.person_id,
                role=candidate.role, occurred_at=candidate.occurred_at, evidence=candidate.evidence,
                status=FlagStatus.open,
            ))
            created += 1
        else:
            flag.occurred_at = candidate.occurred_at
            flag.evidence = candidate.evidence
            updated += 1

    removed = kept_triaged = 0
    for flag in stored.values():
        if flag.status == FlagStatus.open:
            session.delete(flag)
            removed += 1
        else:
            kept_triaged += 1

    session.flush()
    return EngineResult(created=created, updated=updated, removed=removed, kept_triaged=kept_triaged)
