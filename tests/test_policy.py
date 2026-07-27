from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from reliability_control_plane.models import PolicyRule, Severity, SignalEvent, SignalKind
from reliability_control_plane.policy import PolicyEngine, correlate, load_rules, matches


def signal(
    *,
    name: str = "latency_ms",
    value: float | str | bool = 900.0,
    kind: SignalKind = SignalKind.metric,
    seconds: int = 0,
    entity: str = "api-1",
) -> SignalEvent:
    return SignalEvent(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds),
        source="test",
        service="checkout",
        entity=entity,
        kind=kind,
        name=name,
        value=value,
        message="test evidence",
    )


def test_loads_default_policy_pack() -> None:
    rules = load_rules()
    assert len(rules) >= 7
    assert {rule.kind for rule in rules} >= {
        SignalKind.metric,
        SignalKind.log,
        SignalKind.policy,
    }


@pytest.mark.parametrize(
    ("operator", "value", "threshold", "expected"),
    [
        ("gt", 5.0, 4.0, True),
        ("gte", 5.0, 5.0, True),
        ("lt", 4.0, 5.0, True),
        ("lte", 5.0, 5.0, True),
        ("eq", "error", "error", True),
        ("contains", "database timeout", "timeout", True),
        ("truthy", True, True, True),
        ("gt", "not-a-number", 5.0, False),
    ],
)
def test_rule_operators(
    operator: str,
    value: float | str | bool,
    threshold: float | str | bool,
    expected: bool,
) -> None:
    rule = PolicyRule(
        id="operator-test",
        title="Operator test",
        signal_name="sample",
        operator=operator,  # type: ignore[arg-type]
        threshold=threshold,
        severity=Severity.medium,
        recommendation="Inspect it.",
    )
    assert matches(signal(name="sample", value=value), rule) is expected


def test_rule_requires_matching_name_and_kind() -> None:
    rule = PolicyRule(
        id="latency",
        title="Latency",
        signal_name="latency_ms",
        kind=SignalKind.metric,
        operator="gt",
        threshold=750,
        severity=Severity.high,
        recommendation="Inspect latency.",
    )
    assert not matches(signal(name="cpu_pct"), rule)
    assert not matches(signal(kind=SignalKind.log, value=900), rule)


def test_minimum_occurrence_and_window_are_enforced() -> None:
    rule = PolicyRule(
        id="latency",
        title="Sustained latency",
        signal_name="latency_ms",
        kind=SignalKind.metric,
        operator="gt",
        threshold=750,
        severity=Severity.high,
        minimum_occurrences=3,
        window_seconds=60,
        recommendation="Inspect latency.",
    )
    engine = PolicyEngine([rule])

    assert engine.evaluate([signal(seconds=0), signal(seconds=10)]) == []
    violations = engine.evaluate(
        [signal(seconds=0), signal(seconds=20), signal(seconds=40), signal(seconds=180)]
    )
    assert violations == []

    violations = engine.evaluate([signal(seconds=0), signal(seconds=20), signal(seconds=40)])
    assert len(violations) == 1
    assert violations[0].evidence_count == 3


def test_correlates_metric_and_log_evidence_into_one_incident() -> None:
    rules = [
        PolicyRule(
            id="latency",
            title="Latency",
            signal_name="latency_ms",
            operator="gt",
            threshold=750,
            severity=Severity.high,
            recommendation="Inspect dependency timings.",
        ),
        PolicyRule(
            id="error",
            title="Timeout",
            signal_name="service_error",
            kind=SignalKind.log,
            operator="contains",
            threshold="timeout",
            severity=Severity.high,
            recommendation="Inspect downstream health.",
        ),
    ]
    events = [
        signal(value=950),
        signal(name="service_error", value="database timeout", kind=SignalKind.log),
    ]
    incident = correlate(PolicyEngine(rules).evaluate(events))[0]

    assert incident.score == 84
    assert incident.severity == Severity.high
    assert incident.title == "Correlated reliability risk in api-1"
    assert incident.signal_kinds == [SignalKind.log, SignalKind.metric]
    assert "metric threshold" in incident.root_cause_hint
    assert len(incident.recommended_actions) == 2


def test_policy_signal_produces_security_root_cause() -> None:
    rule = PolicyRule(
        id="exposure",
        title="Exposure",
        signal_name="public_admin_exposure",
        kind=SignalKind.policy,
        operator="truthy",
        threshold=True,
        severity=Severity.critical,
        recommendation="Restrict the path.",
    )
    event = signal(
        name="public_admin_exposure",
        value=True,
        kind=SignalKind.policy,
        entity="gateway",
    )
    incident = correlate(PolicyEngine([rule]).evaluate([event]))[0]
    assert incident.severity == Severity.critical
    assert "configuration control" in incident.root_cause_hint
    assert incident.id.startswith("inc-")
