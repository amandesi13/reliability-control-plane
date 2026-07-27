from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

import uvicorn

from .control_plane import ReliabilityControlPlane
from .simulator import SCENARIOS, simulate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rcp",
        description="Reliability Control Plane command-line interface.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Start the API and operator dashboard.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--reload", action="store_true")

    run = subparsers.add_parser("simulate", help="Run a scenario and print the findings.")
    run.add_argument("scenario", choices=SCENARIOS)
    run.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        uvicorn.run(
            "reliability_control_plane.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
        return 0

    control_plane = ReliabilityControlPlane()
    control_plane.ingest(simulate(args.scenario))
    overview = control_plane.overview()
    if args.as_json:
        print(json.dumps(overview.model_dump(mode="json"), indent=2))
    else:
        print(
            f"Scenario: {args.scenario}\n"
            f"Risk score: {overview.risk_score}/100\n"
            f"Incidents: {overview.open_incidents}\n"
            f"Signals: {overview.signals_processed}\n"
            f"Error budget remaining: {overview.slo.error_budget_remaining_pct:.1f}%"
        )
        for incident in overview.incidents:
            print(f"\n[{incident.severity.value.upper()}] {incident.title}")
            print(f"  {incident.summary}")
            print(f"  Next: {incident.recommended_actions[0]}")
    return 0
