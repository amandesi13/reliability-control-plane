from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


SEVERITY_SCORE: dict[Severity, int] = {
    Severity.low: 18,
    Severity.medium: 42,
    Severity.high: 68,
    Severity.critical: 90,
}


class SignalKind(StrEnum):
    metric = "metric"
    log = "log"
    policy = "policy"


class SignalEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=utc_now)
    source: str = Field(min_length=1, max_length=80)
    service: str = Field(min_length=1, max_length=80)
    entity: str = Field(min_length=1, max_length=120)
    kind: SignalKind
    name: str = Field(min_length=1, max_length=120)
    value: float | str | bool
    unit: str | None = Field(default=None, max_length=32)
    message: str = Field(default="", max_length=500)
    attributes: dict[str, Any] = Field(default_factory=dict)


Operator = Literal["gt", "gte", "lt", "lte", "eq", "contains", "truthy"]


class PolicyRule(BaseModel):
    id: str
    title: str
    signal_name: str
    operator: Operator
    threshold: float | str | bool
    severity: Severity
    recommendation: str
    description: str = ""
    kind: SignalKind | None = None
    minimum_occurrences: int = Field(default=1, ge=1, le=100)
    window_seconds: int = Field(default=60, ge=1, le=3600)
    labels: list[str] = Field(default_factory=list)


class Violation(BaseModel):
    rule_id: str
    rule_title: str
    severity: Severity
    service: str
    entity: str
    kind: SignalKind
    signal_name: str
    observed_value: float | str | bool
    threshold: float | str | bool
    timestamp: datetime
    evidence_count: int
    message: str
    recommendation: str


class Incident(BaseModel):
    id: str
    fingerprint: str
    service: str
    entity: str
    severity: Severity
    score: int = Field(ge=0, le=100)
    status: Literal["open", "acknowledged", "resolved"] = "open"
    title: str
    summary: str
    root_cause_hint: str
    started_at: datetime
    updated_at: datetime
    signal_kinds: list[SignalKind]
    violations: list[Violation]
    recommended_actions: list[str]


class SloStatus(BaseModel):
    target_pct: float = 99.9
    observed_pct: float
    error_budget_remaining_pct: float
    request_samples: int
    state: Literal["healthy", "at-risk", "exhausted"]


class Overview(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    risk_score: int
    open_incidents: int
    critical_incidents: int
    services_observed: int
    signals_processed: int
    policy_rules: int
    slo: SloStatus
    incidents: list[Incident]


class SignalBatch(BaseModel):
    signals: list[SignalEvent] = Field(min_length=1, max_length=500)
