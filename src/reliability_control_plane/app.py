from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .control_plane import ReliabilityControlPlane
from .metrics import ReliabilityMetrics
from .models import Incident, Overview, PolicyRule, SignalBatch, SignalEvent
from .simulator import SCENARIOS, simulate


def create_app(*, seed_demo: bool = True) -> FastAPI:
    control_plane = ReliabilityControlPlane()
    metrics = ReliabilityMetrics()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if seed_demo and not control_plane.signals:
            control_plane.ingest(simulate("full-demo"))
        metrics.update(control_plane.overview())
        yield

    app = FastAPI(
        title="Reliability Control Plane",
        version="1.0.0",
        summary="Correlate telemetry and policy drift into explainable incidents.",
        lifespan=lifespan,
    )
    app.state.control_plane = control_plane
    app.state.metrics = metrics
    static_dir = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "component": "reliability-control-plane"}

    @app.get("/api/overview", response_model=Overview)
    def overview() -> Overview:
        snapshot = control_plane.overview()
        metrics.update(snapshot)
        return snapshot

    @app.get("/api/incidents", response_model=list[Incident])
    def incidents(min_score: int = Query(default=0, ge=0, le=100)) -> list[Incident]:
        return [incident for incident in control_plane.incidents if incident.score >= min_score]

    @app.get("/api/signals", response_model=list[SignalEvent])
    def signals(limit: int = Query(default=100, ge=1, le=1000)) -> list[SignalEvent]:
        return control_plane.signals[-limit:][::-1]

    @app.get("/api/policies", response_model=list[PolicyRule])
    def policies() -> list[PolicyRule]:
        return control_plane.engine.rules

    @app.post("/api/signals", response_model=Overview, status_code=202)
    def ingest(batch: SignalBatch) -> Overview:
        control_plane.ingest(batch.signals)
        snapshot = control_plane.overview()
        metrics.update(snapshot)
        return snapshot

    @app.post("/api/simulate/{scenario}", response_model=Overview)
    def run_scenario(scenario: str) -> Overview:
        if scenario not in SCENARIOS:
            raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario}")
        control_plane.reset()
        control_plane.ingest(simulate(scenario))
        snapshot = control_plane.overview()
        metrics.update(snapshot)
        return snapshot

    @app.post("/api/reset", response_model=Overview)
    def reset() -> Overview:
        control_plane.reset()
        snapshot = control_plane.overview()
        metrics.update(snapshot)
        return snapshot

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        metrics.update(control_plane.overview())
        return Response(metrics.render(), media_type="text/plain; version=0.0.4")

    return app


app = create_app()
