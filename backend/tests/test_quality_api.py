"""GET /api/quality on the demo data, as of its as_of."""

from collections import Counter

import pytest

pytestmark = pytest.mark.usefixtures("demo_flags")

ARJUN, OMAR, JIN = 2, 4, 7


@pytest.fixture(scope="module")
def report(client) -> dict:
    response = client.get("/api/quality")
    assert response.status_code == 200, response.text
    return response.json()


def row(report: dict, person_id: int) -> dict:
    return next(r for r in report["people"] if r["person"]["id"] == person_id)


def test_period_and_thresholds(report):
    assert (report["as_of"], report["since"], report["weeks"]) == ("2026-10-09T18:00:00Z", "2026-07-17T18:00:00Z", 12)
    assert (report["big_pr_lines"], report["escape_window_days"]) == (300, 14)


def test_rows_are_developers_by_name(report):
    names = [r["person"]["name"] for r in report["people"]]
    assert len(names) == 7 and names == sorted(names)


def test_omar_approves_fastest_says_least_and_escapes_most(report):
    omar = row(report, OMAR)
    others = [r for r in report["people"] if r["person"]["id"] != OMAR]
    assert omar["minutes_per_100_lines"] < min(r["minutes_per_100_lines"] for r in others)
    assert omar["substantive_share"] < min(r["substantive_share"] for r in others)
    assert omar["comments_per_100_lines"] < min(r["comments_per_100_lines"] for r in others)
    assert omar["escape_rate"] > max(r["escape_rate"] for r in others)
    assert (omar["big_approvals"], omar["stamped_big_approvals"]) == (7, 7)
    assert (omar["approved_merged"], omar["escapes"], omar["escape_rate"]) == (18, 2, 0.111)


def test_team_medians(report):
    assert report["medians"] == {
        "minutes_per_100_lines": 192.0,
        "comments_per_100_lines": 1.21,
        "substantive_share": 0.844,
        "escape_rate": 0.0,
    }


def test_rubber_stamps_and_escapes_agree_with_the_flags(client, report):
    """Every flag in the period, whatever its triage status."""
    def flagged(rule_key: str) -> Counter:
        flags = client.get("/api/flags", params={"rule_key": rule_key}).json()
        return Counter(f["person"]["id"] for f in flags if f["occurred_at"] > report["since"])

    stamped = Counter({r["person"]["id"]: r["stamped_big_approvals"] for r in report["people"]})
    escapes = Counter({r["person"]["id"]: r["escapes"] for r in report["people"]})
    assert +stamped == flagged("rubber_stamp") == Counter({OMAR: 7, JIN: 1})
    assert +escapes == flagged("escape") == Counter({OMAR: 2, ARJUN: 1})


def test_weeks_parameter(client, report):
    short = client.get("/api/quality", params={"weeks": 4}).json()
    assert short["since"] == "2026-09-11T18:00:00Z"
    assert sum(r["approvals"] for r in short["people"]) < sum(r["approvals"] for r in report["people"])
    assert client.get("/api/quality", params={"weeks": 53}).status_code == 422


def test_quality_is_manager_only(client):
    assert client.get("/api/quality", headers={"X-Viewer-Id": str(OMAR)}).status_code == 403
