FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv pip install --system -e ".[dev]"

COPY app ./app
COPY tests ./tests
# Alembic config + migrations — needed for `alembic upgrade head` during
# the /promote-to-alpha step 5. Without these, alembic can't find its
# script_location and the migration step fails with "No 'script_location'
# key found in configuration". `init_schema()` covers the schema on
# first DB touch, but Alembic is the formal migration record.
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
