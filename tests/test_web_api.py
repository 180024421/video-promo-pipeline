from __future__ import annotations

from fastapi.testclient import TestClient

import web_app


def test_health_and_version():
    client = TestClient(web_app.app)
    h = client.get("/api/health")
    assert h.status_code == 200
    assert "checks" in h.json()

    v = client.get("/api/version")
    assert v.status_code == 200
    assert v.json()["version"] == web_app.APP_VERSION


def test_setup_wizard_api():
    client = TestClient(web_app.app)
    r = client.get("/api/setup-wizard")
    assert r.status_code == 200
    assert "steps" in r.json()
