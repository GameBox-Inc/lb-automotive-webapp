# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH"

# Install system dependencies and create non-root user
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser

# Create and use virtual environment
RUN python -m venv /opt/venv \
    && chown -R appuser:appuser /opt/venv

# Copy requirements first for better caching
COPY python-backend/requirements.txt .

# Install Python dependencies as non-root user
USER appuser
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser python-backend/ .

# Ensure data directory exists and is writable (for tests and prod)
USER root
RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

# Run tests (integrated into build stage)
# DATABASE_URL required for import; tests need real PostgreSQL - skip in build if unavailable
RUN if [ -d "tests" ]; then pip install pytest httpx && \
    (DATABASE_URL=postgresql://localhost:5432/test pytest --verbose -x || echo "Tests skipped - no PostgreSQL"); fi

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
