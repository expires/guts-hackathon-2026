.DEFAULT_GOAL := run
.PHONY: run test lint fmt openapi

run:
	uv sync
	uv run uvicorn playyourself.api.app:app --reload --reload-dir src --port 8000

test:
	uv run pytest -q

lint:
	uv run ruff check . && uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

openapi:
	uv run python -m playyourself.api.export_openapi
