.PHONY: run test lint docker-up generate-data

lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy src

test:
	uv run pytest --cov=src --cov-report=term-missing

# Explicit one-off generation, e.g. before `make run` on a fresh checkout.
# Override via SAMPLE_DATA_SEED / SAMPLE_DATA_NUM_EVENTS / SAMPLE_DATA_DAYS /
# LOCAL_DATA_DIR env vars.
generate-data:
	uv run python -m tools.generate_data \
		--seed $${SAMPLE_DATA_SEED:-42} \
		--num-events $${SAMPLE_DATA_NUM_EVENTS:-2000} \
		--days $${SAMPLE_DATA_DAYS:-3} \
		--output-dir $${LOCAL_DATA_DIR:-./data}

# On by default so `make run` alone is a working single-command demo. Set
# GENERATE_SAMPLE_DATA=false if you already have your own dataset in
# LOCAL_DATA_DIR and don't want it overwritten on every start (same knob the
# Docker image reads -- see docker-entrypoint.sh).
run:
	uv sync
	@if [ "$${GENERATE_SAMPLE_DATA:-true}" = "true" ]; then \
		$(MAKE) generate-data; \
	fi
	uv run uvicorn pool_selector.api.app:app --host 0.0.0.0 --port $${PORT:-5050}

docker-up:
	docker compose up --build
