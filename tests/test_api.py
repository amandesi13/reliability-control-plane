from __future__ import annotations

from fastapi.testclient import TestClient

from reliability_control_plane.app import create_app


def test_dashboard_health_and_openapi() -> None:
    with TestClient(create_app(seed_demo=False)) as client:
        assert client.get("/").status_code == 200
        assert "Reliability Control Plane" in client.get("/").text
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/openapi.json").json()["info"]["version"] == "1.0.0"


def test_scenario_endpoint_populates_dashboard_data() -> None:
    with TestClient(create_app(seed_demo=False)) as client:
        response = client.post("/api/simulate/dependency-failure")
        assert response.status_code == 200
        overview = response.json()
        assert overview["risk_score"] >= 80
        assert overview["open_incidents"] == 1

        incidents = client.get("/api/incidents", params={"min_score": 60}).json()
        signals = client.get("/api/signals", params={"limit": 5}).json()
        policies = client.get("/api/policies").json()
        assert len(incidents) == 1
        assert len(signals) == 5
        assert len(policies) >= 7


def test_ingest_reset_metrics_and_invalid_scenario() -> None:
    with TestClient(create_app(seed_demo=False)) as client:
        batch = {
            "signals": [
                {
                    "source": "test",
                    "service": "api",
                    "entity": "api-1",
                    "kind": "policy",
                    "name": "public_admin_exposure",
                    "value": True,
                }
            ]
        }
        response = client.post("/api/signals", json=batch)
        assert response.status_code == 202
        assert response.json()["critical_incidents"] == 1

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "rcp_open_incidents 1.0" in metrics.text

        assert client.post("/api/simulate/unknown").status_code == 404
        reset = client.post("/api/reset").json()
        assert reset["signals_processed"] == 0
        assert reset["open_incidents"] == 0


def test_seeded_app_starts_with_demo_evidence() -> None:
    with TestClient(create_app()) as client:
        overview = client.get("/api/overview").json()
        assert overview["signals_processed"] > 0
        assert overview["open_incidents"] == 3
