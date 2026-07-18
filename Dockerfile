# Python 3.14 per pyproject.toml/.python-version.
# Fallback to a 3.13 base here if a 3.14 wheel/build issue ever appears upstream.
FROM python:3.14-slim

# uv: the package manager this project is built and locked with (uv.lock).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies first (frozen, no dev deps) so this layer is cached
# independently of application source code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY tools ./tools
COPY README.md ./
RUN uv sync --frozen --no-dev

COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Informational default -- the actual bound port is read from $PORT at
# container start (docker-entrypoint.sh), so platforms that assign their own
# port (e.g. Render) work without a Dockerfile change.
EXPOSE 5050

ENTRYPOINT ["./docker-entrypoint.sh"]
