from __future__ import annotations

from reliability_control_plane.control_plane import ReliabilityControlPlane
from reliability_control_plane.simulator import SCENARIOS, simulate


def test_healthy_scenario_has_no_incidents() -> None:
    control_plane = ReliabilityControlPlane()
    control_plane.ingest(simulate("healthy"))
    overview = control_plane.overview()

    assert overview.risk_score == 0
    assert overview.open_incidents == 0
    assert overview.slo.state == "healthy"
    assert overview.slo.error_budget_remaining_pct == 100


def test_full_demo_correlates_three_operational_domains() -> None:
    control_plane = ReliabilityControlPlane()
    incidents = control_plane.ingest(simulate("full-demo"))
    overview = control_plane.overview()

    assert len(incidents) == 3
    assert overview.risk_score == 100
    assert overview.critical_incidents >= 1
    assert overview.services_observed == 3
    assert overview.signals_processed > 60
    assert overview.slo.state == "exhausted"


def test_signal_retention_and_reset() -> None:
    control_plane = ReliabilityControlPlane(max_signals=5)
    control_plane.ingest(simulate("healthy")[:8])
    assert len(control_plane.signals) == 5

    control_plane.reset()
    assert control_plane.signals == []
    assert control_plane.incidents == []
    assert control_plane.overview().signals_processed == 0


def test_all_named_scenarios_are_valid() -> None:
    for scenario in SCENARIOS:
        assert simulate(scenario)


def test_unknown_scenario_is_rejected() -> None:
    try:
        simulate("meteor")
    except ValueError as error:
        assert "unknown scenario" in str(error)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError")
