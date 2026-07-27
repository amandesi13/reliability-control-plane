from __future__ import annotations

from threading import RLock
from typing import Literal

from .models import Incident, Overview, SignalEvent, SloStatus
from .policy import PolicyEngine, correlate


class ReliabilityControlPlane:
    def __init__(self, engine: PolicyEngine | None = None, max_signals: int = 5000) -> None:
        self.engine = engine or PolicyEngine()
        self.max_signals = max_signals
        self._signals: list[SignalEvent] = []
        self._incidents: list[Incident] = []
        self._lock = RLock()

    @property
    def signals(self) -> list[SignalEvent]:
        with self._lock:
            return list(self._signals)

    @property
    def incidents(self) -> list[Incident]:
        with self._lock:
            return list(self._incidents)

    def ingest(self, events: list[SignalEvent]) -> list[Incident]:
        with self._lock:
            self._signals.extend(events)
            self._signals = self._signals[-self.max_signals :]
            self._incidents = correlate(self.engine.evaluate(self._signals))
            return list(self._incidents)

    def reset(self) -> None:
        with self._lock:
            self._signals.clear()
            self._incidents.clear()

    def slo_status(self) -> SloStatus:
        request_events = [event for event in self.signals if event.name == "request_result"]
        if not request_events:
            return SloStatus(
                observed_pct=100.0,
                error_budget_remaining_pct=100.0,
                request_samples=0,
                state="healthy",
            )

        errors = sum(str(event.value).casefold() != "ok" for event in request_events)
        observed = 100 * (1 - errors / len(request_events))
        allowed_error_pct = 0.1
        actual_error_pct = 100 - observed
        remaining = max(0.0, 100 * (1 - actual_error_pct / allowed_error_pct))
        state: Literal["healthy", "at-risk", "exhausted"]
        state = "healthy" if remaining > 50 else "at-risk" if remaining > 0 else "exhausted"
        return SloStatus(
            observed_pct=round(observed, 3),
            error_budget_remaining_pct=round(remaining, 1),
            request_samples=len(request_events),
            state=state,
        )

    def overview(self) -> Overview:
        incidents = self.incidents
        signals = self.signals
        return Overview(
            risk_score=max((incident.score for incident in incidents), default=0),
            open_incidents=len(incidents),
            critical_incidents=sum(incident.severity.value == "critical" for incident in incidents),
            services_observed=len({event.service for event in signals}),
            signals_processed=len(signals),
            policy_rules=len(self.engine.rules),
            slo=self.slo_status(),
            incidents=incidents,
        )
