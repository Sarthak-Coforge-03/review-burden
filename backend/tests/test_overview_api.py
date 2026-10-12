"""GET /api/overview on the demo data, as of its as_of."""

import pytest

pytestmark = pytest.mark.usefixtures("demo_flags")

OMAR = 4


@pytest.fixture(scope="module")
def overview(client) -> dict:
    response = client.get("/api/overview")
    assert response.status_code == 200, response.text
    return response.json()


def test_window(overview):
    assert (overview["as_of"], overview["since"], overview["window_days"]) == (
        "2026-10-09T18:00:00Z", "2026-09-11T18:00:00Z", 28,
    )
    assert (overview["escape_rate_floor"], overview["top2_share_threshold"], overview["stale_after_hours"]) == (
        0.1, 0.6, 48,
    )


def test_parts_and_score(overview):
    parts = {p["key"]: (p["good"], p["total"], p["score"]) for p in overview["parts"]}
    assert parts == {
        "coverage": (97, 101, 96),
        "depth": (12, 16, 75),  # Omar's four stamps in the window
        "escapes": (95, 97, 79),  # the fixes for PRs 148 and 188
        "responsiveness": (128, 130, 98),
        "load_balance": (51, 147, 87),  # same 147 reviews and 65% top-two share as the load page
    }
    assert sum(p["weight"] for p in overview["parts"]) == pytest.approx(1)
    assert overview["score"] == 86


def test_kpis_match_the_flags_and_load_pages(client, overview):
    open_flags = client.get("/api/flags", params={"status": "open"}).json()
    load = client.get("/api/load").json()
    kpis = overview["kpis"]
    assert kpis["open_flags"] == len(open_flags)
    assert (kpis["prs_merged"], kpis["median_hours_to_first_review"]) == (101, 3.8)
    assert kpis["waiting_reviews"] == sum(r["pending"] for r in load["people"]) == 6
    assert kpis["stale_reviews"] == 2


def test_trend_is_weekly_and_ends_now(overview):
    trend = overview["trend"]
    assert [t["as_of"][:10] for t in trend] == [
        "2026-08-21", "2026-08-28", "2026-09-04", "2026-09-11", "2026-09-18", "2026-09-25", "2026-10-02", "2026-10-09",
    ]  # earlier weeks would reach back before the first PR
    assert trend[-1] == {"as_of": overview["as_of"], "score": overview["score"]}
    assert [t["score"] for t in trend] == [94, 92, 85, 86, 87, 88, 87, 86]


def test_weeks_parameter(client):
    short = client.get("/api/overview", params={"weeks": 3}).json()
    assert [t["score"] for t in short["trend"]] == [88, 87, 86]
    assert client.get("/api/overview", params={"weeks": 0}).status_code == 422


def test_overview_is_manager_only(client):
    assert client.get("/api/overview", headers={"X-Viewer-Id": str(OMAR)}).status_code == 403
