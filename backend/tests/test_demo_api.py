"""Resetting the demo from the API, after the kind of changes a live demo makes."""

import pytest

OMAR = 4
ROWS = {"developers": 8, "pull_requests": 253, "reviews": 351, "review_comments": 491, "review_requests": 309}
DEMO = {"rows": ROWS, "flags": 22, "open_flags": 19}

pytestmark = pytest.mark.usefixtures("demo_flags")


def flag_statuses(client) -> dict[tuple, str]:
    return {
        (f["rule_key"], (f["pull_request"] or {}).get("id"), (f["person"] or {}).get("id")): f["status"]
        for f in client.get("/api/flags").json()
    }


def test_reset_undoes_triage_and_settings(client):
    before = flag_statuses(client)
    defaults = client.get("/api/settings").json()["defaults"]

    open_stamp = next(f for f in client.get("/api/flags", params={"status": "open"}).json())
    client.patch(f"/api/flags/{open_stamp['id']}", json={"status": "dismissed", "dismiss_reason": "Demo."})
    client.put("/api/settings", json=defaults | {"rubber_stamp_min_lines": 100_000})
    assert flag_statuses(client) != before

    response = client.post("/api/demo/reset")
    assert response.status_code == 200, response.text
    assert response.json() == DEMO
    assert flag_statuses(client) == before
    settings = client.get("/api/settings").json()
    assert settings["values"] == settings["defaults"]


def test_reset_is_manager_only(client):
    before = flag_statuses(client)
    assert client.post("/api/demo/reset", headers={"X-Viewer-Id": str(OMAR)}).status_code == 403
    assert flag_statuses(client) == before
