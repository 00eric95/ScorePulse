# =============================================================================
# ScorePulse AI - Production Dockerfile with Celery + Redis support
# =============================================================================

# ─── Build Stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# ─── Final Stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Environment variables
# PYTHONDONTWRITEBYTECODE=1 prevents caching of compiled .pyc files
# This ensures workers always get fresh imports without stale cache
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production \
    FLASK_APP=run.py \
    PYTHONPATH=/app:/app/soccer_match_prediction

# Create non-root user
RUN useradd -m -r appuser && \
    mkdir -p /app/instance /app/logs /app/static/uploads && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code (with correct ownership)
COPY --chown=appuser:appuser . .

# Install curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Switch to non-root
USER appuser

# Expose ports (Flask + Flower)
EXPOSE 5000 5555

# Healthcheck for web (overridden per service in compose)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Default command (overridden in compose)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--threads", "2", "run:app"]

