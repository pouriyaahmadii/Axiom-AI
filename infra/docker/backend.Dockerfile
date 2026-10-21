# Multi-stage Dockerfile for AgentOps Backend (FastAPI & Celery)
FROM python:3.10.15-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY services/backend/ services/backend/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Runtime Stage
FROM python:3.10.15-slim-bookworm AS runner

WORKDIR /app/services/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: unprivileged non-root user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/bash -m appuser

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY services/backend/ /app/services/backend/

RUN chown -R appuser:appuser /app

ENV PYTHONPATH="/app/services/backend"
ENV PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
