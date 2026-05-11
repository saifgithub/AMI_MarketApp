#!/usr/bin/env bash
# Run the AMI Trade dev stack — backend + iPhone app — in one shot.
#
# Usage:
#   scripts/run_dev.sh            # start backend + run on TESTING IPHONE 13
#   scripts/run_dev.sh simulator  # start backend + run on iOS simulator
#   scripts/run_dev.sh backend    # start ONLY the backend
#   scripts/run_dev.sh device-id  # any other arg: pass to flutter run -d

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
MOBILE_DIR="${PROJECT_ROOT}/mobile"

TARGET="${1:-TESTING IPHONE 13}"

# Detect Mac's LAN IP so the iPhone can reach the backend
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)
if [[ -z "$LAN_IP" ]]; then
  echo "⚠ Couldn't detect LAN IP — using localhost (only works for simulator)"
  LAN_IP="localhost"
fi

API_URL="http://${LAN_IP}:8000"

echo "▶ Backend will listen at: ${API_URL}"
echo "▶ Flutter target: ${TARGET}"
echo ""

# ── Start backend (background) ───────────────────────────────────────────

start_backend() {
  cd "${BACKEND_DIR}"

  # Pick a Python — prefer 3.13, fall back to system python3
  if command -v python3.13 &>/dev/null; then
    PYTHON_BIN="python3.13"
  elif [[ -x "/opt/homebrew/opt/python@3.13/bin/python3.13" ]]; then
    PYTHON_BIN="/opt/homebrew/opt/python@3.13/bin/python3.13"
  else
    PYTHON_BIN="python3"
  fi
  echo "▶ Using Python: $($PYTHON_BIN --version)"

  # Set up venv on first run
  if [[ ! -d ".venv" ]]; then
    echo "▶ Creating Python venv (first run)…"
    "$PYTHON_BIN" -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install --quiet --upgrade pip
    pip install -e ".[dev]" --quiet
  else
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi

  # Already running?
  if curl -sf "${API_URL}/v1/health" >/dev/null 2>&1; then
    echo "✓ Backend already running at ${API_URL}"
    return 0
  fi

  echo "▶ Starting backend on 0.0.0.0:8000…"
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload >/tmp/ami-backend.log 2>&1 &
  BACKEND_PID=$!
  echo "  PID: $BACKEND_PID  (logs: /tmp/ami-backend.log)"
  echo "  Save this PID — stop with: kill $BACKEND_PID"

  # Wait for it to come up
  for _ in {1..20}; do
    if curl -sf "${API_URL}/v1/health" >/dev/null 2>&1; then
      echo "✓ Backend healthy"
      return 0
    fi
    sleep 0.5
  done

  echo "✗ Backend didn't respond within 10s. Check /tmp/ami-backend.log"
  return 1
}

# ── Run Flutter ──────────────────────────────────────────────────────────

run_flutter() {
  cd "${MOBILE_DIR}"
  echo ""
  echo "▶ Running Flutter on ${TARGET} (API: ${API_URL})…"
  echo "  Once running:"
  echo "    r → hot reload"
  echo "    R → hot restart"
  echo "    q → quit"
  echo ""
  flutter run -d "${TARGET}" --dart-define=AMI_API_URL="${API_URL}"
}

# ── Dispatch ─────────────────────────────────────────────────────────────

case "${TARGET}" in
  backend)
    start_backend
    echo ""
    echo "✓ Backend running. Visit http://localhost:8000/docs for API explorer."
    echo "  Tail logs: tail -f /tmp/ami-backend.log"
    ;;
  *)
    start_backend
    run_flutter
    ;;
esac
