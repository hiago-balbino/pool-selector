FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY tools ./tools
COPY README.md ./
RUN uv sync --frozen --no-dev

COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Informational default - the actual bound port is read from $PORT at
# container start (docker-entrypoint.sh), so platforms that assign their own
# port (e.g. Render) work without a Dockerfile change.
EXPOSE 5050

ENTRYPOINT ["./docker-entrypoint.sh"]
