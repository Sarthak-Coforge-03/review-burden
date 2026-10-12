"""GET /api/load on the demo data, as of its as_of."""

import pytest

ARJUN, OMAR = 2, 4


@pytest.fixture(scope="module")
def report(client) -> dict:
    response = client.get("/api/load")
    assert response.status_code == 200, response.text
    return response.json()


def row(report: dict, person_id: int) -> dict:
    return next(r for r in report["people"] if r["person"]["id"] == person_id)


def test_team_numbers_match_the_load_rule(report):
    assert (report["team_reviews"], report["team_median"], report["window_days"]) == (147, 13, 28)
    assert report["top2_share"] == 0.653
    assert (report["top2_share_threshold"], report["median_multiple_threshold"]) == (0.6, 2.0)
    assert report["concentrated"] is True


def test_arjun_is_the_busiest_reviewer(report):
    arjun = report["people"][0]
    assert arjun["person"]["id"] == ARJUN
    assert (arjun["reviews"], arjun["share"], arjun["median_multiple"]) == (82, 0.558, 6.31)
    assert arjun["over_median_multiple"] is True
    assert (arjun["pending"], arjun["oldest_pending_hours"]) == (6, 175.7)


def test_everyone_else_is_within_bounds_and_has_nothing_waiting(report):
    others = [r for r in report["people"] if r["person"]["id"] != ARJUN]
    assert not any(r["over_median_multiple"] for r in others)
    assert all((r["pending"], r["oldest_pending_hours"]) == (0, None) for r in others)


def test_rows_are_developers_busiest_first(report):
    assert len(report["people"]) == 7
    assert all(r["person"]["role"] == "dev" for r in report["people"])
    reviews = [r["reviews"] for r in report["people"]]
    assert reviews == sorted(reviews, reverse=True)


def test_weekly_history_lines_up_with_the_window(report):
    assert len(report["week_starts"]) == 12
    assert report["week_starts"][-1] == "2026-10-02T18:00:00Z"
    for r in report["people"]:
        assert len(r["weekly"]) == 12
        assert sum(r["weekly"][-4:]) == r["reviews"]  # the last 4 weeks are the 28-day window


def test_weeks_parameter(client):
    short = client.get("/api/load", params={"weeks": 4}).json()
    assert len(short["week_starts"]) == 4
    assert all(len(r["weekly"]) == 4 for r in short["people"])
    assert client.get("/api/load", params={"weeks": 0}).status_code == 422


def test_load_is_manager_only(client):
    assert client.get("/api/load", headers={"X-Viewer-Id": str(OMAR)}).status_code == 403
