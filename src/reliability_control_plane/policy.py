from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import (
    SEVERITY_SCORE,
    Incident,
    PolicyRule,
    Severity,
    SignalEvent,
    SignalKind,
    Violation,
)


def load_rules(path: Path | None = None) -> list[PolicyRule]:
    policy_path = path or Path(__file__).with_name("policies") / "default.json"
    data: dict[str, Any] = json.loads(policy_path.read_text(encoding="utf-8"))
    return [PolicyRule.model_validate(item) for item in data["rules"]]


def matches(event: SignalEvent, rule: PolicyRule) -> bool:
    if event.name != rule.signal_name:
        return False
    if rule.kind is not None and event.kind != rule.kind:
        return False

    value = event.value
    threshold = rule.threshold
    if rule.operator == "truthy":
        return bool(value)
    if rule.operator == "contains":
        return str(threshold).casefold() in str(value).casefold()
    if rule.operator == "eq":
        return value == threshold

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        return False
    operators = {
        "gt": value > threshold,
        "gte": value >= threshold,
        "lt": value < threshold,
        "lte": value <= threshold,
    }
    return operators[rule.operator]


class PolicyEngine:
    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        self.rules = rules or load_rules()

    def evaluate(self, events: list[SignalEvent]) -> list[Violation]:
        ordered = sorted(events, key=lambda event: event.timestamp)
        violations: list[Violation] = []

        for rule in self.rules:
            candidates = [event for event in ordered if matches(event, rule)]
            grouped: dict[tuple[str, str], list[SignalEvent]] = defaultdict(list)
            for event in candidates:
                grouped[(event.service, event.entity)].append(event)

            for (service, entity), entity_events in grouped.items():
                latest = entity_events[-1]
                window_start = latest.timestamp.timestamp() - rule.window_seconds
                evidence = [
                    event for event in entity_events if event.timestamp.timestamp() >= window_start
                ]
                if len(evidence) < rule.minimum_occurrences:
                    continue
                violations.append(
                    Violation(
                        rule_id=rule.id,
                        rule_title=rule.title,
                        severity=rule.severity,
                        service=service,
                        entity=entity,
                        kind=latest.kind,
                        signal_name=latest.name,
                        observed_value=latest.value,
                        threshold=rule.threshold,
                        timestamp=latest.timestamp,
                        evidence_count=len(evidence),
                        message=latest.message or rule.description or rule.title,
                        recommendation=rule.recommendation,
                    )
                )

        return sorted(
            violations,
            key=lambda item: (SEVERITY_SCORE[item.severity], item.timestamp),
            reverse=True,
        )


def _root_cause_hint(kinds: set[SignalKind], violations: list[Violation]) -> str:
    if {SignalKind.metric, SignalKind.log, SignalKind.policy}.issubset(kinds):
        return (
            "Runtime degradation and policy drift are present together. "
            "Validate the latest configuration change before scaling the service."
        )
    if {SignalKind.metric, SignalKind.log}.issubset(kinds):
        return (
            "The metric threshold and application errors share an entity and time window. "
            "Inspect saturation, retries, and downstream dependency health."
        )
    if SignalKind.policy in kinds:
        return (
            "A configuration control failed. Compare deployed policy with the approved baseline "
            "and restrict the exposed path."
        )
    names = {violation.signal_name for violation in violations}
    if {"dl_prb_utilization_pct", "packet_loss_pct"} & names:
        return (
            "The radio cell shows congestion or weak-channel characteristics. "
            "Inspect load distribution, SINR, and handover behaviour."
        )
    return "Inspect the newest evidence first, then compare it with the last known-good deployment."


def correlate(violations: list[Violation]) -> list[Incident]:
    grouped: dict[tuple[str, str], list[Violation]] = defaultdict(list)
    for violation in violations:
        grouped[(violation.service, violation.entity)].append(violation)

    incidents: list[Incident] = []
    for (service, entity), evidence in grouped.items():
        evidence.sort(key=lambda item: item.timestamp)
        kinds = {item.kind for item in evidence}
        max_base = max(SEVERITY_SCORE[item.severity] for item in evidence)
        score = min(100, max_base + (len(evidence) - 1) * 6 + (len(kinds) - 1) * 10)
        if score >= 85:
            severity = Severity.critical
        elif score >= 60:
            severity = Severity.high
        elif score >= 35:
            severity = Severity.medium
        else:
            severity = Severity.low

        digest_source = f"{service}:{entity}:{','.join(sorted(item.rule_id for item in evidence))}"
        fingerprint = hashlib.sha1(digest_source.encode(), usedforsecurity=False).hexdigest()
        actions = list(dict.fromkeys(item.recommendation for item in evidence))
        title = (
            f"Correlated reliability risk in {entity}"
            if len(evidence) > 1
            else evidence[0].rule_title
        )
        incidents.append(
            Incident(
                id=f"inc-{fingerprint[:10]}",
                fingerprint=fingerprint,
                service=service,
                entity=entity,
                severity=severity,
                score=score,
                title=title,
                summary=(
                    f"{len(evidence)} policy checks failed across "
                    f"{len(kinds)} signal {'type' if len(kinds) == 1 else 'types'}."
                ),
                root_cause_hint=_root_cause_hint(kinds, evidence),
                started_at=evidence[0].timestamp,
                updated_at=evidence[-1].timestamp,
                signal_kinds=sorted(kinds, key=lambda item: item.value),
                violations=evidence,
                recommended_actions=actions,
            )
        )

    return sorted(incidents, key=lambda item: (item.score, item.updated_at), reverse=True)
