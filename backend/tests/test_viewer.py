"""The viewer dependencies, exercised through a throwaway app so they are tested on their own."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.deps import ManagerDep, ViewerDep
from backend.schemas import Person

probe = FastAPI()


@probe.get("/whoami")
def whoami(viewer: ViewerDep) -> Person:
    return Person.model_validate(viewer)


@probe.get("/manager-only")
def manager_only(viewer: ManagerDep) -> Person:
    return Person.model_validate(viewer)


@pytest.fixture(scope="module")
def probe_client():
    return TestClient(probe)


def test_without_a_header_the_viewer_is_the_manager(probe_client):
    assert probe_client.get("/whoami").json() == {"id": 1, "name": "Maya Chen", "role": "manager"}


def test_header_picks_the_viewer(probe_client):
    assert probe_client.get("/whoami", headers={"X-Viewer-Id": "4"}).json()["name"] == "Omar Haddad"


def test_unknown_viewer_is_rejected(probe_client):
    assert probe_client.get("/whoami", headers={"X-Viewer-Id": "999"}).status_code == 401


def test_malformed_viewer_is_rejected(probe_client):
    assert probe_client.get("/whoami", headers={"X-Viewer-Id": "maya"}).status_code == 422


def test_manager_only_routes_reject_developers(probe_client):
    assert probe_client.get("/manager-only").status_code == 200
    response = probe_client.get("/manager-only", headers={"X-Viewer-Id": "4"})
    assert response.status_code == 403
    assert response.json() == {"detail": "Only the manager can do this"}
