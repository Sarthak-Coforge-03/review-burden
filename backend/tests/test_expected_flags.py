"""End to end: seeding the demo (data, rule engine, triage) must reproduce data/expected_flags.json
exactly: every flag and its evidence, the counts, the load numbers and the repeat patterns."""

import json
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict

import pytest
from sqlalchemy import select

from backend import clock
from backend.db import SessionLocal
from backend.models import Flag, FlagStatus, RuleKey
from backend.rules.params import DEFAULT_PARAMS
from backend.rules.patterns import active_patterns
from backend.seed import DEFAULT_SEED_PATH, seed_demo

EXPECTED = json.loads((DEFAULT_SEED_PATH.parent / "expected_flags.json").read_text())


def plain_key(rule_key, pr_id, person_id, role) -> tuple:
    return (str(rule_key), pr_id, person_id, None if role is None else str(role))


@pytest.fixture(scope="module")
def flags(seed_data, triage_data) -> Iterator[list[Flag]]:
    """The demo as `python -m backend.seed` builds it, in a transaction rolled back after this module."""
    with SessionLocal() as session:
        seed_demo(session, seed_data, triage_data)
        session.expire_all()  # read evidence back from the database, not the objects that wrote it
        yield list(session.scalars(select(Flag)))
        session.rollback()


def test_clock_defaults_to_the_data_as_of():
    assert clock.now().isoformat().replace("+00:00", "Z") == EXPECTED["as_of"]


@pytest.mark.parametrize("rule_key", list(RuleKey))
def test_rule_matches_expected_flags(rule_key, flags):
    got = {plain_key(*f.key): f.evidence for f in flags if f.rule_key == rule_key}
    want = {
        plain_key(f["rule_key"], f["pr_id"], f["person_id"], f["role"]): f["evidence"]
        for f in EXPECTED["flags"]
        if f["rule_key"] == rule_key
    }

    assert want, f"no expected flags for {rule_key}"
    assert got.keys() == want.keys()
    for key, evidence in want.items():
        # Rules may record more evidence than the generator's verifier, never less or different.
        assert evidence.items() <= got[key].items(), key


def test_flag_counts_match(flags):
    assert Counter(str(f.rule_key) for f in flags) == EXPECTED["flag_counts"]


def test_load_numbers_match(flags):
    [load] = [f for f in flags if f.rule_key == RuleKey.load_concentration]
    for field in ("counts", "top2_share", "median", "over_median_multiple"):
        assert load.evidence[field] == EXPECTED["load"][field], field


def test_triage_is_applied_and_everything_else_is_open(flags, triage_data):
    want = {plain_key(t["rule_key"], t["pr_id"], t["person_id"], t["role"]): t for t in triage_data}
    for flag in flags:
        entry = want.get(plain_key(*flag.key))
        if entry is None:
            assert flag.status == FlagStatus.open
        else:
            assert flag.status == entry["status"]
            assert flag.note == entry.get("note")
            assert flag.dismiss_reason == entry.get("dismiss_reason")


def test_repeat_patterns_match(flags):
    found = [
        {**asdict(p), "role": str(p.role), "rule_key": str(p.rule_key), "pr_ids": list(p.pr_ids)}
        for p in active_patterns(flags, clock.now(), DEFAULT_PARAMS)
    ]
    order = lambda p: (p["person_id"], p["rule_key"])  # noqa: E731
    assert sorted(found, key=order) == sorted(EXPECTED["repeat_patterns"], key=order)
