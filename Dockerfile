FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM node:22.18.0-bookworm-slim AS node

FROM python:3.13.5-slim-bookworm AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-cache

FROM python:3.13.5-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates libopus0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 bot
COPY --from=node /usr/local/bin/node /usr/local/bin/node
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FFMPEG_PATH=/usr/bin/ffmpeg
WORKDIR /app
COPY --from=dependencies /app/.venv /app/.venv
COPY zixona/ ./zixona/
USER bot
CMD ["python", "-m", "zixona"]
