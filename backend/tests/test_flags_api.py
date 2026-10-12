"""GET /api/flags and PATCH /api/flags/{id}."""

import pytest
from sqlalchemy import delete, select

from backend.db import SessionLocal
from backend.models import Flag
from backend.rules.engine import run_engine
from backend.seed import apply_triage

OMAR, ARJUN = 4, 2
AS_OMAR = {"X-Viewer-Id": str(OMAR)}


@pytest.fixture(scope="module", autouse=True)
def demo_flags(triage_data):
    """The seeded demo flags, committed for this module and removed afterwards: other modules expect none."""
    with SessionLocal.begin() as session:
        run_engine(session)
        apply_triage(session, triage_data)
    yield
    with SessionLocal.begin() as session:
        session.execute(delete(Flag))


def flag_id(rule_key: str, pr_id: int, person_id: int) -> int:
    with SessionLocal() as session:
        return session.scalar(
            select(Flag.id).where(Flag.rule_key == rule_key, Flag.pr_id == pr_id, Flag.person_id == person_id)
        )


def keys(flags: list[dict]) -> set[tuple]:
    return {(f["rule_key"], f["pull_request"] and f["pull_request"]["id"], f["person"] and f["person"]["id"]) for f in flags}


# ---------------------------------------------------------------- listing

def test_manager_sees_every_flag_newest_first(client):
    flags = client.get("/api/flags").json()
    assert len(flags) == 22
    assert [f["occurred_at"] for f in flags] == sorted((f["occurred_at"] for f in flags), reverse=True)


def test_flags_carry_person_pr_and_evidence(client):
    [stamp] = client.get("/api/flags", params={"rule_key": "rubber_stamp", "person_id": OMAR, "status": "dismissed"}).json()
    assert stamp["person"] == {"id": OMAR, "name": "Omar Haddad", "role": "dev"}
    assert stamp["role"] == "reviewer"
    assert stamp["pull_request"]["id"] == 151
    assert stamp["evidence"] == {"lines": 882, "seconds_to_approve": 103, "substantive_comments": 0}
    assert stamp["dismiss_reason"].startswith("Live pairing session")


def test_team_level_flag_has_no_person_or_pr(client):
    [load] = client.get("/api/flags", params={"rule_key": "load_concentration"}).json()
    assert load["person"] is None and load["pull_request"] is None and load["role"] is None
    assert load["evidence"]["over_median_multiple"] == [ARJUN]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"status": "acknowledged"}, 2),
        ({"rule_key": "rubber_stamp"}, 8),
        ({"person_id": ARJUN}, 3),
        ({"rule_key": "rubber_stamp", "status": "open"}, 7),
    ],
)
def test_filters(client, params, expected):
    assert len(client.get("/api/flags", params=params).json()) == expected


def test_unknown_filter_value_is_rejected(client):
    assert client.get("/api/flags", params={"status": "resolved"}).status_code == 422


def test_developer_sees_only_their_own_flags(client):
    flags = client.get("/api/flags", headers=AS_OMAR).json()
    assert len(flags) == 9  # 7 rubber stamps + 2 escapes
    assert {f["person"]["id"] for f in flags} == {OMAR}


def test_developer_cannot_ask_for_someone_else(client):
    assert client.get("/api/flags", params={"person_id": ARJUN}, headers=AS_OMAR).status_code == 403
    assert len(client.get("/api/flags", params={"person_id": OMAR}, headers=AS_OMAR).json()) == 9


# ---------------------------------------------------------------- triage

def test_acknowledge_with_a_note(client):
    fid = flag_id("stale_backlog", 222, ARJUN)
    response = client.patch(f"/api/flags/{fid}", json={"status": "acknowledged", "note": "  Asked Lena to take it. "})
    assert response.status_code == 200
    assert response.json()["status"] == "acknowledged"
    assert response.json()["note"] == "Asked Lena to take it."
    assert ("stale_backlog", 222, ARJUN) in keys(client.get("/api/flags", params={"status": "acknowledged"}).json())


def test_dismissing_requires_a_reason(client):
    fid = flag_id("stale_backlog", 230, ARJUN)
    assert client.patch(f"/api/flags/{fid}", json={"status": "dismissed"}).status_code == 422
    assert client.patch(f"/api/flags/{fid}", json={"status": "dismissed", "dismiss_reason": "   "}).status_code == 422

    response = client.patch(f"/api/flags/{fid}", json={"status": "dismissed", "dismiss_reason": "On leave that week."})
    assert response.json()["dismiss_reason"] == "On leave that week."


def test_reopening_clears_the_reason_and_keeps_an_omitted_note(client):
    fid = flag_id("escape", 148, ARJUN)
    client.patch(f"/api/flags/{fid}", json={"status": "dismissed", "dismiss_reason": "Flaky test.", "note": "Check CI."})

    reopened = client.patch(f"/api/flags/{fid}", json={"status": "open"}).json()
    assert reopened["status"] == "open"
    assert reopened["dismiss_reason"] is None
    assert reopened["note"] == "Check CI."

    cleared = client.patch(f"/api/flags/{fid}", json={"status": "open", "note": None}).json()
    assert cleared["note"] is None


def test_developers_cannot_triage(client):
    fid = flag_id("rubber_stamp", 23, OMAR)
    assert client.patch(f"/api/flags/{fid}", json={"status": "acknowledged"}, headers=AS_OMAR).status_code == 403


def test_unknown_flag_is_404(client):
    assert client.patch("/api/flags/99999", json={"status": "acknowledged"}).status_code == 404
