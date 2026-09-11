"""API tests in demo mode: REST routes, command flow, event store, WebSocket snapshot."""
from __future__ import annotations

import os

import pytest

os.environ["DEMO_MODE"] = "true"
os.environ["DB_PATH"] = ":memory:"
os.environ["DASHBOARD_TOKEN"] = "t0k"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

H = {"Authorization": "Bearer t0k"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_and_auth(client):
    assert client.get("/api/health").json()["demo"] is True
    assert client.get("/api/state").status_code == 401
    assert client.get("/api/state", headers=H).status_code == 200
    assert client.get("/api/state?token=t0k").status_code == 200


def test_state_has_all_demo_systems(client):
    st = client.get("/api/state", headers=H).json()
    assert set(st) == {"solaredge", "panasonic", "zte", "rainbird", "broadlink_ac", "hik_nvr", "doorbell"}
    assert all(v["online"] for v in st.values())


def test_command_flow_and_events(client):
    r = client.post("/api/rainbird/command", json={"command": "run_zone", "args": {"zone": 2, "minutes": 3}}, headers=H)
    assert r.status_code == 200 and r.json()["state"]["data"]["active_zone"] == 2
    bad = client.post("/api/rainbird/command", json={"command": "run_zone", "args": {"zone": 99}}, headers=H)
    assert bad.status_code == 400
    assert client.post("/api/nothing/command", json={"command": "x"}, headers=H).status_code == 404
    ev = client.get("/api/events?system=rainbird", headers=H).json()
    kinds = [e["kind"] for e in ev]
    assert "command" in kinds and "state" in kinds


def test_websocket_snapshot(client):
    with client.websocket_connect("/ws?token=t0k") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "snapshot" and "rainbird" in msg["state"] and len(msg["systems"]) == 7
