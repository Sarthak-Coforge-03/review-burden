"""The rules, run on the seeded data, must find exactly the planted problems in data/expected_flags.json."""

import json
from collections import Counter

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend import clock
from backend.db import SessionLocal
from backend.models import Developer, PullRequest, Review, ReviewRequest, RuleKey
from backend.rules.params import DEFAULT_PARAMS
from backend.rules.pr_rules import PR_RULES
from backend.rules.types import FlagCandidate
from backend.rules.window_rules import load_concentration, stale_backlog
from backend.seed import DEFAULT_SEED_PATH

EXPECTED = json.loads((DEFAULT_SEED_PATH.parent / "expected_flags.json").read_text())


def flag_key(rule_key, pr_id, person_id, role) -> tuple:
    return (str(rule_key), pr_id, person_id, None if role is None else str(role))


@pytest.fixture(scope="module")
def found(seeded_db) -> list[FlagCandidate]:
    now = clock.now()
    with SessionLocal() as session:
        prs = session.scalars(
            select(PullRequest).options(selectinload(PullRequest.reviews).selectinload(Review.comments))
        ).all()
        requests = session.scalars(select(ReviewRequest).options(selectinload(ReviewRequest.pull_request))).all()
        reviews = session.scalars(select(Review)).all()
        developers = session.scalars(select(Developer)).all()
    flags = [f for rule in PR_RULES for f in rule(prs, DEFAULT_PARAMS)]
    flags += stale_backlog(requests, now, DEFAULT_PARAMS)
    flags += load_concentration(reviews, developers, now, DEFAULT_PARAMS)
    return flags


def test_clock_defaults_to_the_data_as_of():
    assert clock.now().isoformat().replace("+00:00", "Z") == EXPECTED["as_of"]


@pytest.mark.parametrize("rule_key", list(RuleKey))
def test_rule_matches_expected_flags(rule_key, found):
    got = {flag_key(*f.key): f.evidence for f in found if f.rule_key == rule_key}
    want = {
        flag_key(f["rule_key"], f["pr_id"], f["person_id"], f["role"]): f["evidence"]
        for f in EXPECTED["flags"]
        if f["rule_key"] == rule_key
    }

    assert want, f"no expected flags for {rule_key}"
    assert got.keys() == want.keys()
    for key, evidence in want.items():
        # Rules may record more evidence than the generator's verifier, never less or different.
        assert evidence.items() <= got[key].items(), key


def test_flag_counts_match(found):
    assert Counter(str(f.rule_key) for f in found) == EXPECTED["flag_counts"]


def test_no_two_flags_share_an_identity(found):
    assert len({f.key for f in found}) == len(found)


def test_load_numbers_match(found):
    [load] = [f for f in found if f.rule_key == RuleKey.load_concentration]
    assert load.evidence["counts"] == EXPECTED["load"]["counts"]
    assert load.evidence["top2_share"] == EXPECTED["load"]["top2_share"]
    assert load.evidence["median"] == EXPECTED["load"]["median"]
    assert load.evidence["over_median_multiple"] == EXPECTED["load"]["over_median_multiple"]
