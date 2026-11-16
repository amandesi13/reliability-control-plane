"""The Pages demo answers /api calls from web/bridge.py; it must match the real API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from reliability_control_plane.app import create_app

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))

import bridge  # noqa: E402

VOLATILE = {"id", "generated_at", "detected_at", "timestamp", "first_seen", "last_seen"}


def _stable(value: object) -> object:
    """Drop generated ids and wall-clock times, which differ between two runs."""
    if isinstance(value, dict):
        return {k: _stable(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


CALLS = [
    ("POST", "/api/simulate/dependency-failure"),
    ("GET", "/api/overview"),
    ("GET", "/api/incidents?min_score=60"),
    ("GET", "/api/signals?limit=5"),
    ("GET", "/api/policies"),
    ("POST", "/api/simulate/full-demo"),
    ("GET", "/api/overview"),
    ("POST", "/api/reset"),
    ("GET", "/api/signals"),
]


def test_bridge_matches_fastapi_for_the_dashboard_calls() -> None:
    demo = bridge.DemoApi(seed_demo=False)
    with TestClient(create_app(seed_demo=False)) as client:
        for method, url in CALLS:
            expected = client.request(method, url)
            status, body = demo.handle(method, url)
            assert status == expected.status_code, url
            assert _stable(body) == _stable(expected.json()), url


@pytest.mark.parametrize(
    ("method", "url", "status"),
    [
        ("POST", "/api/simulate/nope", 404),
        ("GET", "/api/signals?limit=0", 422),
        ("GET", "/api/incidents?min_score=101", 422),
        ("GET", "/api/signals?limit=abc", 422),
        ("DELETE", "/api/overview", 404),
        ("GET", "/api/unknown", 404),
    ],
)
def test_bridge_rejects_what_the_api_rejects(method: str, url: str, status: int) -> None:
    assert bridge.DemoApi(seed_demo=False).handle(method, url)[0] == status


def test_module_entry_point_is_seeded_and_returns_json() -> None:
    reply = json.loads(bridge.handle("GET", "/api/overview"))
    assert reply["status"] == 200
    assert reply["body"]["open_incidents"] >= 1
    assert reply["body"]["signals_processed"] > 0
