"""The rules, run on the seeded data, must find exactly the planted problems in data/expected_flags.json."""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models import PullRequest, Review
from backend.rules.params import DEFAULT_PARAMS
from backend.rules.pr_rules import PR_RULES
from backend.seed import DEFAULT_SEED_PATH

EXPECTED = json.loads((DEFAULT_SEED_PATH.parent / "expected_flags.json").read_text())


def expected_for(rule_key: str) -> dict[tuple, dict]:
    return {
        (f["rule_key"], f["pr_id"], f["person_id"], f["role"]): f["evidence"]
        for f in EXPECTED["flags"]
        if f["rule_key"] == rule_key
    }


@pytest.fixture(scope="module")
def all_prs(seeded_db):
    from backend.db import SessionLocal

    with SessionLocal() as session:
        return session.scalars(
            select(PullRequest).options(selectinload(PullRequest.reviews).selectinload(Review.comments))
        ).all()


@pytest.mark.parametrize("rule", PR_RULES, ids=lambda rule: rule.__name__)
def test_pr_rule_matches_expected_flags(rule, all_prs):
    found = {
        (f.rule_key.value, f.pr_id, f.person_id, f.role.value): f.evidence
        for f in rule(all_prs, DEFAULT_PARAMS)
    }
    expected = expected_for(rule.__name__)

    assert expected, f"no expected flags for {rule.__name__}"
    assert found.keys() == expected.keys()
    for key, evidence in expected.items():
        # Rules may record more evidence than the generator's verifier, never less or different.
        assert evidence.items() <= found[key].items(), key
