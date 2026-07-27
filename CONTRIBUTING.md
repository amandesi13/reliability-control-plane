# Contributing

## Local setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

Activate the virtual environment, then run:

```bash
ruff check .
mypy
pytest
```

## Pull requests

- Keep policy rules deterministic and explainable.
- Add a focused test for every new detector or correlation path.
- Do not add an automated remediation that changes infrastructure by default.
- Update the API or architecture documentation when contracts change.

## Commit style

Use a short imperative summary, such as `Add restart-loop detector`.
