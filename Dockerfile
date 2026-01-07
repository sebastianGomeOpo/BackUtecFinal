# ============================================================================
# DOCKERFILE PARA FASTAPI + UVICORN
# Proyecto: BlackCombinator - Backend API
# ============================================================================

FROM python:3.11-slim

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Set PYTHONPATH para que src sea importable
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .


# Health check (usa 8080 por defecto para App Runner)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Expose port (App Runner usa 8080 por defecto)
EXPOSE 8080

# Start application with Uvicorn
# Using 1 worker for now (App Runner manages scaling)
# Lee PORT de App Runner (por defecto 8080 para compatibilidad)
CMD uvicorn src.presentation.api:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --workers 1
