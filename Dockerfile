FROM python:3.14-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE.txt ./
COPY tracarbon tracarbon

RUN uv sync --locked --no-editable --extra all

FROM python:3.14-slim-trixie

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["tracarbon", "run"]
