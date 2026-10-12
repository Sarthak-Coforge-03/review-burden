"""run_engine against the seeded database. Each test's session is rolled back when it closes."""

import json
from dataclasses import replace
from datetime import timedelta

from sqlalchemy import func, select

from backend import clock
from backend.db import SessionLocal
from backend.models import Flag, FlagStatus, RuleKey
from backend.rules.engine import EngineResult, run_engine
from backend.rules.params import DEFAULT_PARAMS
from backend.seed import DEFAULT_SEED_PATH, load_seed

EXPECTED = json.loads((DEFAULT_SEED_PATH.parent / "expected_flags.json").read_text())
EXPECTED_KEYS = {(f["rule_key"], f["pr_id"], f["person_id"], f["role"]) for f in EXPECTED["flags"]}
TOTAL = len(EXPECTED_KEYS)
NO_RUBBER_STAMPS = replace(DEFAULT_PARAMS, rubber_stamp_min_lines=100_000)


def stored_keys(session) -> set[tuple]:
    return {
        (str(f.rule_key), f.pr_id, f.person_id, None if f.role is None else str(f.role))
        for f in session.scalars(select(Flag))
    }


def flag_count(session) -> int:
    return session.scalar(select(func.count()).select_from(Flag))


def get_flag(session, rule_key: RuleKey, pr_id: int, person_id: int) -> Flag:
    return session.scalar(select(Flag).where(Flag.rule_key == rule_key, Flag.pr_id == pr_id, Flag.person_id == person_id))


def test_first_run_stores_the_expected_flags_as_open(session):
    assert run_engine(session) == EngineResult(created=TOTAL, updated=0, removed=0, kept_triaged=0)
    assert stored_keys(session) == EXPECTED_KEYS
    assert set(session.scalars(select(Flag.status))) == {FlagStatus.open}


def test_rerun_updates_in_place_without_duplicates(session):
    run_engine(session)
    assert run_engine(session) == EngineResult(created=0, updated=TOTAL, removed=0, kept_triaged=0)
    assert flag_count(session) == TOTAL
    # Team-level flags have NULL identity columns, which the unique constraint cannot police.
    assert session.scalar(select(func.count()).where(Flag.rule_key == RuleKey.load_concentration)) == 1


def test_rerun_refreshes_evidence(session):
    run_engine(session)
    stale = get_flag(session, RuleKey.stale_backlog, 230, 2)
    assert stale.evidence == {"waiting_hours": 75.9}

    run_engine(session, now=clock.now() + timedelta(hours=1))
    assert stale.evidence == {"waiting_hours": 76.9}


def test_triage_survives_a_rerun(session):
    run_engine(session)
    stamp = get_flag(session, RuleKey.rubber_stamp, 151, 4)
    stamp.status = FlagStatus.dismissed
    stamp.dismiss_reason = "Live pairing session."
    stamp.evidence = {}

    run_engine(session)
    assert stamp.status == FlagStatus.dismissed
    assert stamp.dismiss_reason == "Live pairing session."
    assert stamp.evidence["lines"] == 882


def test_open_flags_that_stop_firing_are_removed_triaged_ones_kept(session):
    run_engine(session)
    acknowledged = get_flag(session, RuleKey.rubber_stamp, 99, 4)
    acknowledged.status = FlagStatus.acknowledged
    acknowledged.note = "Raised in retro."

    result = run_engine(session, params=NO_RUBBER_STAMPS)
    assert result == EngineResult(created=0, updated=TOTAL - 8, removed=7, kept_triaged=1)
    remaining = list(session.scalars(select(Flag).where(Flag.rule_key == RuleKey.rubber_stamp)))
    assert remaining == [acknowledged]
    assert acknowledged.note == "Raised in retro."

    # When the rule fires again, the open ones come back and the triaged one is reused, not duplicated.
    assert run_engine(session) == EngineResult(created=7, updated=TOTAL - 7, removed=0, kept_triaged=0)
    assert flag_count(session) == TOTAL
    assert acknowledged.status == FlagStatus.acknowledged


def test_reseeding_clears_flags(seed_data):
    with SessionLocal.begin() as session:
        run_engine(session)
    with SessionLocal.begin() as session:
        load_seed(session, seed_data)
        assert flag_count(session) == 0
