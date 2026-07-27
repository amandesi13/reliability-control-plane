.PHONY: install check test run docker

install:
	python -m pip install -e ".[dev]"

check:
	ruff check .
	mypy
	pytest

test:
	pytest

run:
	rcp serve --reload

docker:
	docker compose up --build
