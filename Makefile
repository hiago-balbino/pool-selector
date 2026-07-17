.PHONY: run test lint docker-up

lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy src

test:
	uv run pytest --cov=src --cov-report=term-missing

run:
	@echo "make run: placeholder — replaced once the FastAPI app exists"

docker-up:
	@echo "make docker-up: placeholder — replaced once Dockerfile/docker-compose.yml exist"
