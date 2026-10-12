import copy
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from backend.db import SessionLocal
from backend.models import PullRequest, PullRequestKind
from backend.seed import TABLES, load_seed

EXPECTED_COUNTS = {
    "developers": 8,
    "pull_requests": 253,
    "reviews": 351,
    "review_comments": 491,
    "review_requests": 309,
}


def table_counts(session: Session) -> dict[str, int]:
    return {key: session.scalar(select(func.count()).select_from(model)) for key, model in TABLES}


def test_seed_loads_every_row(session):
    assert table_counts(session) == EXPECTED_COUNTS


def test_reseed_replaces_rows_instead_of_duplicating(seed_data, session):
    with SessionLocal.begin() as s:
        assert load_seed(s, seed_data) == EXPECTED_COUNTS
    assert table_counts(session) == EXPECTED_COUNTS


def test_failed_seed_keeps_existing_data(seed_data, session):
    bad = copy.deepcopy(seed_data)
    bad["developers"][0]["role"] = "boss"
    with pytest.raises(StatementError, match="boss"):
        with SessionLocal.begin() as s:
            load_seed(s, bad)
    assert table_counts(session) == EXPECTED_COUNTS


def test_unknown_field_is_rejected(seed_data):
    bad = copy.deepcopy(seed_data)
    bad["pull_requests"][0]["labels"] = ["urgent"]
    with pytest.raises(KeyError, match="labels"):
        with SessionLocal.begin() as s:
            load_seed(s, bad)


def test_merged_at_and_merged_by_must_be_set_together(seed_data):
    bad = copy.deepcopy(seed_data)
    merged = next(pr for pr in bad["pull_requests"] if pr["merged_at"])
    merged["merged_by_id"] = None
    with pytest.raises(IntegrityError, match="ck_pull_requests_merged_pair"):
        with SessionLocal.begin() as s:
            load_seed(s, bad)


def test_timestamps_come_back_as_utc(session):
    pr = session.get(PullRequest, 1)
    assert pr.opened_at == datetime(2026, 7, 20, 8, 36, 51, tzinfo=timezone.utc)
    assert pr.opened_at.tzinfo is timezone.utc


def test_fix_links_back_to_the_pr_it_fixes(session):
    fix = session.scalar(select(PullRequest).where(PullRequest.fixes_pr_id == 99))
    assert fix.kind is PullRequestKind.hotfix
    assert fix.fixes.id == 99
