from __future__ import annotations

from reliability_control_plane.cli import build_parser, main


def test_cli_summary(capsys: object) -> None:
    assert main(["simulate", "dependency-failure"]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Risk score:" in output
    assert "Correlated reliability risk" in output


def test_cli_json(capsys: object) -> None:
    assert main(["simulate", "healthy", "--json"]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert '"risk_score": 0' in output


def test_parser_exposes_serve_command() -> None:
    args = build_parser().parse_args(["serve", "--port", "9099"])
    assert args.command == "serve"
    assert args.port == 9099
