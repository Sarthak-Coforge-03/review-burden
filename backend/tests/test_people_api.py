"""GET /api/people/profiles and /api/people/{id}/profile, on the demo data as of its as_of."""

import pytest

pytestmark = pytest.mark.usefixtures("demo_flags")

MAYA, ARJUN, OMAR, JIN = 1, 2, 4, 7


def profile(client, person_id: int, viewer: int | None = None) -> dict:
    headers = {"X-Viewer-Id": str(viewer)} if viewer else {}
    response = client.get(f"/api/people/{person_id}/profile", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def counts(summary: dict) -> dict[str, int]:
    return {c["rule_key"]: c["count"] for c in summary["flags"]}


def test_omar_is_a_reviewer_side_rubber_stamper(client):
    omar = profile(client, OMAR)
    assert counts(omar["as_reviewer"]) == {"rubber_stamp": 6, "escape": 2}  # the dismissed PR 151 stamp is left out
    assert omar["as_reviewer"]["open"] == 7  # the PR 99 escape is acknowledged
    assert counts(omar["as_author"]) == {}
    [pattern] = omar["patterns"]
    assert (pattern["rule_key"], pattern["role"], pattern["count"], pattern["window_days"]) == (
        "rubber_stamp", "reviewer", 3, 30,
    )
    assert [pr["id"] for pr in pattern["pull_requests"]] == [188, 209, 247]


def test_jin_has_an_author_side_pattern_and_a_one_off_stamp(client):
    jin = profile(client, JIN)
    assert counts(jin["as_author"]) == {"self_approval": 2}
    assert counts(jin["as_reviewer"]) == {"rubber_stamp": 1}
    assert [(p["rule_key"], p["role"]) for p in jin["patterns"]] == [("self_approval", "author")]
    assert [pr["id"] for pr in jin["patterns"][0]["pull_requests"]] == [213, 240]


def test_arjun_carries_the_review_load_and_the_debt(client):
    arjun = profile(client, ARJUN)
    activity = arjun["activity"]
    assert (activity["reviews_given"], activity["team_reviews"], activity["team_median"]) == (82, 147, 13)
    assert activity["share"] == pytest.approx(82 / 147, abs=0.001)
    assert activity["over_median_multiple"] is True
    assert profile(client, OMAR)["activity"]["over_median_multiple"] is False

    debt = arjun["review_debt"]
    assert [d["pull_request"]["id"] for d in debt][:2] == [222, 230]  # oldest first
    assert [d["pull_request"]["id"] for d in debt if d["stale"]] == [222, 230]
    assert all(d["waiting_hours"] <= 48 for d in debt if not d["stale"])
    assert debt[0]["waiting_hours"] == 175.7


def test_profiles_list_every_developer_but_not_the_manager(client):
    response = client.get("/api/people/profiles")
    assert response.status_code == 200
    people = [p["person"] for p in response.json()]
    assert len(people) == 7
    assert MAYA not in {p["id"] for p in people}
    assert [p["name"] for p in people] == sorted(p["name"] for p in people)


def test_profiles_list_is_manager_only(client):
    assert client.get("/api/people/profiles", headers={"X-Viewer-Id": str(OMAR)}).status_code == 403


def test_developer_sees_only_their_own_profile(client):
    assert profile(client, OMAR, viewer=OMAR)["person"]["id"] == OMAR
    assert client.get(f"/api/people/{ARJUN}/profile", headers={"X-Viewer-Id": str(OMAR)}).status_code == 403


def test_unknown_person_is_404(client):
    assert client.get("/api/people/999/profile").status_code == 404
