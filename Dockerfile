FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir uv && uv sync --locked --no-dev

EXPOSE 10000
CMD ["sh", "scripts/render-start.sh", "agent"]
