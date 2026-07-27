from __future__ import annotations

from prometheus_client import CollectorRegistry, Gauge, generate_latest

from .models import Overview


class ReliabilityMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.risk_score = Gauge(
            "rcp_risk_score",
            "Highest active incident risk score",
            registry=self.registry,
        )
        self.open_incidents = Gauge(
            "rcp_open_incidents",
            "Number of open correlated incidents",
            registry=self.registry,
        )
        self.signals_processed = Gauge(
            "rcp_signals_processed",
            "Number of signals retained by the control plane",
            registry=self.registry,
        )
        self.error_budget = Gauge(
            "rcp_error_budget_remaining_pct",
            "Remaining SLO error budget percentage",
            registry=self.registry,
        )

    def update(self, overview: Overview) -> None:
        self.risk_score.set(overview.risk_score)
        self.open_incidents.set(overview.open_incidents)
        self.signals_processed.set(overview.signals_processed)
        self.error_budget.set(overview.slo.error_budget_remaining_pct)

    def render(self) -> bytes:
        return generate_latest(self.registry)
