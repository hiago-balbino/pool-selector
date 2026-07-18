#!/bin/sh
# Optional sample-data generation before the server starts, controlled by
# GENERATE_SAMPLE_DATA. This script's OWN default (used by a bare `docker
# run`, with no env var set) is "false" -- the safe choice for the image
# used outside this repo's local-dev wrappers. docker-compose.yml and the
# Makefile's `run` target both set GENERATE_SAMPLE_DATA=true explicitly by
# default, so `make docker-up` / `make run` generate data automatically; see
# their own comments to opt back out. Also useful for demo/test deploys with
# an ephemeral filesystem (e.g. Render) where LOCAL_DATA_DIR would otherwise
# be empty on every boot -- regenerating at container start (not image build
# time) keeps event timestamps anchored to "now", so the default recency
# window still finds data.
set -e

if [ "${GENERATE_SAMPLE_DATA:-false}" = "true" ]; then
  echo "GENERATE_SAMPLE_DATA=true -- generating synthetic sample data into ${LOCAL_DATA_DIR:-./data}"
  uv run --no-sync python -m tools.generate_data \
    --seed "${SAMPLE_DATA_SEED:-42}" \
    --num-events "${SAMPLE_DATA_NUM_EVENTS:-2000}" \
    --days "${SAMPLE_DATA_DAYS:-3}" \
    --output-dir "${LOCAL_DATA_DIR:-./data}"
fi

exec uv run --no-sync uvicorn pool_selector.api.app:app --host 0.0.0.0 --port "${PORT:-5050}"
