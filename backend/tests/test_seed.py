import copy
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from backend.db import SessionLocal
from backend.models import Flag, PullRequest, PullRequestKind
from backend.seed import DEFAULT_SEED_PATH, TABLES, load_seed, main, seed_demo

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


def test_naive_timestamps_are_rejected(session):
    query = select(PullRequest).where(PullRequest.opened_at < datetime(2026, 8, 1))
    with pytest.raises(StatementError, match="naive datetime"):
        session.scalars(query).all()


def test_fix_links_back_to_the_pr_it_fixes(session):
    fix = session.scalar(select(PullRequest).where(PullRequest.fixes_pr_id == 99))
    assert fix.kind is PullRequestKind.hotfix
    assert fix.fixes.id == 99


def test_triage_for_a_flag_that_does_not_exist_is_rejected(seed_data, session):
    bogus = [{"rule_key": "rubber_stamp", "pr_id": 1, "person_id": 2, "role": "reviewer", "status": "dismissed"}]
    with pytest.raises(ValueError, match="matches no flag"):
        seed_demo(session, seed_data, bogus)


@pytest.fixture
def remove_flags_afterwards():
    """`main` commits flags; other modules expect an empty flags table."""
    yield
    with SessionLocal.begin() as s:
        s.execute(delete(Flag))


@pytest.mark.usefixtures("remove_flags_afterwards")
def test_command_seeds_the_demo_and_prints_a_summary(capsys, session):
    main([])
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        f"Seeded from {DEFAULT_SEED_PATH}",
        *(f"  {table:<16} {count}" for table, count in EXPECTED_COUNTS.items()),
        "Flags: 22 (2 acknowledged, 1 dismissed, 19 open)",
        "Repeat patterns: 2",
    ]
    assert err == ""
    assert table_counts(session) == EXPECTED_COUNTS


@pytest.mark.usefixtures("remove_flags_afterwards")
def test_command_warns_when_the_data_is_not_as_of_now(seed_data, tmp_path, capsys):
    data = {**seed_data, "as_of": "2026-10-10T18:00:00Z"}
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(data))

    main([str(path)])
    out, err = capsys.readouterr()
    assert f"Seeded from {path}" in out
    assert "dismissed" not in out
    assert err.startswith("Warning: data is as of 2026-10-10T18:00:00Z")
    assert "the rules will use 2026-10-09T18:00:00+00:00 as now" in err
