FROM python:3.13-slim@sha256:bf503bb2243c5aad0aa951544dd60d165f992646441d35dea90893703fc26251

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# CR124/M14: install from the LOCKFILE, not from the version ranges. `uv pip
# install -e ".[dev]"` re-resolved on every rebuild, so two builds of the same
# commit could ship different package versions — and it pulled the dev group
# (pytest, ruff, mypy) into a production image. `--locked` fails the build if
# uv.lock has drifted from pyproject.toml rather than silently re-resolving.
# `alembic` is a MAIN dependency, so `/promote-to-alpha` step 5's
# `alembic upgrade head` still works without the dev group; pytest runs on the
# Mac (promotion step 1), never in this image.
# `--no-install-project` because `app/` is copied below (and bind-mounted over
# at runtime anyway) — without it the setuptools backend would try to build the
# project before its source exists. PYTHONPATH=/app is what makes `app.main`
# importable, not a site-packages install.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
ENV PATH="/app/.venv/bin:$PATH"

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

# CR124/N7: ran as root. Fixed uid/gid so the bug_attachments volume can be
# chown'd to a stable owner.
#
# BEWARE: the named volume already exists on melehost and is root-owned, so the
# chown below only fixes a FRESH volume. An existing one needs
# `docker run --rm -v ami-trade-local_bug_attachments:/d alpine chown -R 1001:1001 /d`
# before this image can accept an upload — runbook step 6. Without it POST
# /v1/feedback/bug fails on write, which is the alpha feedback channel.
RUN groupadd --system --gid 1001 ami \
    && useradd --system --uid 1001 --gid ami --no-create-home ami \
    && mkdir -p /data/bug_attachments /data/.cache \
    && chown -R ami:ami /data /app

# CR124 round 2 / audit MAJOR 3 — `HOME` must point somewhere this uid can write.
#
# `--no-create-home` skips making the directory but still records `/home/ami` in
# passwd, and Docker sets no HOME on a USER switch. So `expanduser("~")` resolved
# to a non-existent dir under root-owned `/home`, and yfinance caches to
# `platformdirs.user_cache_dir()` → `~/.cache/py-yfinance`. It does not crash — it
# catches the OSError, logs via its own plain `logging` logger (not our structlog
# JSON stream) and sets `dummy = True` — but it never memoises the failure, so it
# retried the failing `makedirs` on EVERY call and permanently lost the
# cookie/crumb cache that pyproject's own comment says exists to survive Yahoo's
# rate-limit dance. A silent functional regression introduced by the non-root
# switch: exactly the CR040 shape.
ENV HOME=/data
USER ami

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
