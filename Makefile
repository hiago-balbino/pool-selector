.PHONY: run test lint docker-up generate-data

lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy src

test:
	uv run pytest --cov=src --cov-report=term-missing

generate-data:
	uv run python -m tools.generate_data \
		--seed $${SAMPLE_DATA_SEED:-42} \
		--num-events $${SAMPLE_DATA_NUM_EVENTS:-2000} \
		--days $${SAMPLE_DATA_DAYS:-3} \
		--output-dir $${LOCAL_DATA_DIR:-./data}

run:
	uv sync
	@if [ "$${GENERATE_SAMPLE_DATA:-true}" = "true" ]; then \
		$(MAKE) generate-data; \
	fi
	@if [ -f .env ]; then set -a; . ./.env; set +a; fi; \
	uv run uvicorn pool_selector.api.app:app --host 0.0.0.0 --port $${PORT:-5050}

docker-up:
	docker compose up --build
