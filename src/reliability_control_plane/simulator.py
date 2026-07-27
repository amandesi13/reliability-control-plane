from __future__ import annotations

from datetime import UTC, datetime, timedelta
from random import Random

from .models import SignalEvent, SignalKind

SCENARIOS = ("healthy", "dependency-failure", "ran-congestion", "security-drift", "full-demo")


def _event(
    *,
    timestamp: datetime,
    service: str,
    entity: str,
    kind: SignalKind,
    name: str,
    value: float | str | bool,
    unit: str | None = None,
    message: str = "",
) -> SignalEvent:
    return SignalEvent(
        timestamp=timestamp,
        source="scenario-simulator",
        service=service,
        entity=entity,
        kind=kind,
        name=name,
        value=value,
        unit=unit,
        message=message,
    )


def simulate(scenario: str, seed: int = 7) -> list[SignalEvent]:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {', '.join(SCENARIOS)}")

    rng = Random(seed)
    now = datetime.now(UTC).replace(microsecond=0)
    events: list[SignalEvent] = []
    for index in range(20):
        events.append(
            _event(
                timestamp=now - timedelta(seconds=40 - index * 2),
                service="checkout-api",
                entity="checkout-api-7d9",
                kind=SignalKind.metric,
                name="latency_ms",
                value=round(rng.uniform(120, 260), 2),
                unit="ms",
                message="Request latency sample",
            )
        )
        events.append(
            _event(
                timestamp=now - timedelta(seconds=40 - index * 2),
                service="checkout-api",
                entity="checkout-api-7d9",
                kind=SignalKind.metric,
                name="request_result",
                value="ok",
                message="Request completed",
            )
        )

    if scenario in {"dependency-failure", "full-demo"}:
        for index in range(4):
            at = now - timedelta(seconds=9 - index * 2)
            events.extend(
                [
                    _event(
                        timestamp=at,
                        service="checkout-api",
                        entity="checkout-api-7d9",
                        kind=SignalKind.metric,
                        name="latency_ms",
                        value=980 + index * 130,
                        unit="ms",
                        message="Database call exceeded latency objective",
                    ),
                    _event(
                        timestamp=at,
                        service="checkout-api",
                        entity="checkout-api-7d9",
                        kind=SignalKind.log,
                        name="service_error",
                        value="database timeout",
                        message="PostgreSQL connection pool timed out",
                    ),
                    _event(
                        timestamp=at,
                        service="checkout-api",
                        entity="checkout-api-7d9",
                        kind=SignalKind.metric,
                        name="request_result",
                        value="error",
                        message="Request failed",
                    ),
                ]
            )

    if scenario in {"ran-congestion", "full-demo"}:
        for index in range(3):
            at = now - timedelta(seconds=7 - index * 2)
            events.extend(
                [
                    _event(
                        timestamp=at,
                        service="ran-xapp",
                        entity="cell-berlin-01",
                        kind=SignalKind.metric,
                        name="dl_prb_utilization_pct",
                        value=94 + index,
                        unit="%",
                        message="Downlink resource blocks near saturation",
                    ),
                    _event(
                        timestamp=at,
                        service="ran-xapp",
                        entity="cell-berlin-01",
                        kind=SignalKind.metric,
                        name="packet_loss_pct",
                        value=3.1 + index * 0.4,
                        unit="%",
                        message="Packet loss elevated",
                    ),
                    _event(
                        timestamp=at,
                        service="ran-xapp",
                        entity="cell-berlin-01",
                        kind=SignalKind.metric,
                        name="sinr_db",
                        value=3.4 - index * 0.5,
                        unit="dB",
                        message="Radio quality below target",
                    ),
                ]
            )

    if scenario in {"security-drift", "full-demo"}:
        events.extend(
            [
                _event(
                    timestamp=now - timedelta(seconds=5),
                    service="edge-gateway",
                    entity="gateway-policy-eu1",
                    kind=SignalKind.policy,
                    name="public_admin_exposure",
                    value=True,
                    message="SSH is reachable from 0.0.0.0/0",
                ),
                _event(
                    timestamp=now - timedelta(seconds=3),
                    service="edge-gateway",
                    entity="gateway-policy-eu1",
                    kind=SignalKind.log,
                    name="auth_failure",
                    value="root",
                    message="Repeated root login failures from an untrusted network",
                ),
            ]
        )

    return sorted(events, key=lambda event: event.timestamp)
