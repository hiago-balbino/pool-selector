.PHONY: run test lint docker-up

lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy src

test:
	uv run pytest --cov=src --cov-report=term-missing

run:
	uv sync
	uv run uvicorn pool_selector.api.app:app --host 0.0.0.0 --port 5050

docker-up:
	docker compose up --build
