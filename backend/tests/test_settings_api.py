"""Settings API on the demo data. Saving re-runs the rules, so every test leaves the defaults in place."""

from collections.abc import Iterator

import pytest

OMAR = 4
TOTAL_FLAGS = 22


@pytest.fixture(scope="module", autouse=True)
def back_to_defaults(demo_flags, client) -> Iterator[None]:
    yield
    client.delete("/api/settings")


@pytest.fixture
def defaults(client) -> dict:
    return client.get("/api/settings").json()["defaults"]


def stamps(client) -> dict[int, str]:
    flags = client.get("/api/flags", params={"rule_key": "rubber_stamp"}).json()
    return {f["pull_request"]["id"]: f["status"] for f in flags}


def test_defaults_are_in_effect(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["values"] == body["defaults"]
    assert body["defaults"]["rubber_stamp_min_lines"] == 300
    assert body["defaults"]["stock_phrases"] == ["+1", "approved", "lgtm", "looks good", "nit", "ship it", "👍"]


def test_saving_re_runs_the_rules_and_keeps_triaged_flags(client, defaults):
    assert len(stamps(client)) == 8
    response = client.put("/api/settings", json=defaults | {"rubber_stamp_min_lines": 100_000})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["values"]["rubber_stamp_min_lines"] == 100_000
    assert body["engine"] == {
        "created": 0, "updated": TOTAL_FLAGS - 8, "removed": 7, "kept_triaged": 1, "open_flags": 19 - 7,
    }
    assert stamps(client) == {151: "dismissed"}  # the dismissed one keeps its reason
    assert client.get("/api/settings").json()["values"]["rubber_stamp_min_lines"] == 100_000
    assert client.get("/api/quality").json()["big_pr_lines"] == 100_000  # reports use the saved settings

    reset = client.delete("/api/settings").json()
    assert reset["values"] == reset["defaults"]
    assert (reset["engine"]["created"], reset["engine"]["removed"], reset["engine"]["open_flags"]) == (7, 0, 19)
    assert len(stamps(client)) == 8


def test_stock_phrases_are_cleaned_up(client, defaults):
    body = client.put("/api/settings", json=defaults | {"stock_phrases": [" LGTM ", "lgtm", "", "Nice"]}).json()
    assert body["values"]["stock_phrases"] == ["lgtm", "nice"]
    client.delete("/api/settings")


@pytest.mark.parametrize(
    "change",
    [
        {"health_weight_coverage": 0.35},  # weights add up to 110%
        {"load_top2_share": 1.0},
        {"rubber_stamp_min_lines": 0},
        {"pattern_min_count": 1},
    ],
)
def test_invalid_settings_are_rejected_and_nothing_changes(client, defaults, change):
    response = client.put("/api/settings", json=defaults | change)
    assert response.status_code == 422
    assert client.get("/api/settings").json()["values"] == defaults


def test_weights_error_says_what_is_wrong(client, defaults):
    detail = client.put("/api/settings", json=defaults | {"health_weight_coverage": 0.35}).json()["detail"]
    assert "must add up to 100%, not 110%" in detail[0]["msg"]


def test_re_running_with_unchanged_settings_changes_nothing(client):
    response = client.post("/api/settings/run-engine")
    assert response.status_code == 200
    assert response.json() == {"created": 0, "updated": TOTAL_FLAGS, "removed": 0, "kept_triaged": 0, "open_flags": 19}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/settings"),
        ("PUT", "/api/settings"),
        ("DELETE", "/api/settings"),
        ("POST", "/api/settings/run-engine"),
    ],
)
def test_settings_are_manager_only(client, defaults, method, path):
    body = defaults if method == "PUT" else None
    response = client.request(method, path, json=body, headers={"X-Viewer-Id": str(OMAR)})
    assert response.status_code == 403
