"""Browser stand-in for the HTTP API, used by the GitHub Pages demo.

The static demo has no server, so the page runs the real control plane in
Pyodide (Python compiled to WebAssembly) and routes the dashboard's
`fetch("/api/...")` calls here. Routes, query limits and response bodies
mirror `reliability_control_plane.app`; tests/test_web_bridge.py checks that
both return the same JSON.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel

from reliability_control_plane.control_plane import ReliabilityControlPlane
from reliability_control_plane.simulator import SCENARIOS, simulate

Response = tuple[int, Any]


def _dump(value: BaseModel | list[Any]) -> Any:
    if isinstance(value, list):
        return [item.model_dump(mode="json") for item in value]
    return value.model_dump(mode="json")


def _int_param(query: dict[str, list[str]], name: str, default: int, low: int, high: int) -> int:
    raw = query.get(name, [str(default)])[-1]
    value = int(raw)
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


class DemoApi:
    """In-memory equivalent of the FastAPI app's /api routes."""

    def __init__(self, *, seed_demo: bool = True) -> None:
        self.control_plane = ReliabilityControlPlane()
        if seed_demo:
            self.control_plane.ingest(simulate("full-demo"))

    def handle(self, method: str, url: str) -> Response:
        parts = urlsplit(url)
        path = parts.path.rstrip("/")
        query = parse_qs(parts.query)
        method = method.upper()
        cp = self.control_plane
        try:
            if method == "GET" and path == "/api/overview":
                return 200, _dump(cp.overview())
            if method == "GET" and path == "/api/incidents":
                min_score = _int_param(query, "min_score", 0, 0, 100)
                return 200, _dump([i for i in cp.incidents if i.score >= min_score])
            if method == "GET" and path == "/api/signals":
                limit = _int_param(query, "limit", 100, 1, 1000)
                return 200, _dump(cp.signals[-limit:][::-1])
            if method == "GET" and path == "/api/policies":
                return 200, _dump(cp.engine.rules)
            if method == "POST" and path.startswith("/api/simulate/"):
                scenario = path.removeprefix("/api/simulate/")
                if scenario not in SCENARIOS:
                    return 404, {"detail": f"Unknown scenario: {scenario}"}
                cp.reset()
                cp.ingest(simulate(scenario))
                return 200, _dump(cp.overview())
            if method == "POST" and path == "/api/reset":
                cp.reset()
                return 200, _dump(cp.overview())
        except ValueError as exc:
            return 422, {"detail": str(exc)}
        return 404, {"detail": "Not Found"}


_api = DemoApi()


def handle(method: str, url: str) -> str:
    """Entry point for JavaScript: returns {"status": int, "body": ...} as JSON."""
    status, body = _api.handle(method, url)
    return json.dumps({"status": status, "body": body})
