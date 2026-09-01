#!/bin/sh
# register_ami_vllm.sh — import the on-prem vLLM into a DEDICATED Kimi Code config home (CR215).
#
# WHY A SEPARATE HOME: the coder (Qwen, Alibaba) and the foreign auditor (kimi-code/k3, Moonshot)
# are different roles that need different settings — and `[thinking] effort` is a GLOBAL key in
# config.toml that overrides any per-model `default_effort`. Sharing one config file would make
# every launch mutate a flag the other role reads: exactly the shared-mutable-flag race CLAUDE.md
# forbids. `KIMI_CODE_HOME` gives each role a disjoint config path instead. The auditor keeps the
# default `~/.kimi-code` (OAuth, k3); the coder gets its own, holding no credentials at all.
#
# WHY THE REGISTRY IS IN-REPO: DEF387 was "version-control the supervisors — the guard's other half
# lived on one disk". A provider definition that exists only in an untracked ~/.kimi-code/config.toml
# is that same defect. `ami_vllm_api.json` is the source of truth; this script is the only thing that
# turns it into machine state, and it is re-runnable.
#
# USAGE:  sh orchestration/harness/register_ami_vllm.sh
# Exit:   0 registered + round-trip verified · 2 bad usage · 3 vLLM unavailable or wrong model
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
API_JSON="$HERE/ami_vllm_api.json"
KIMI_BIN="${AMI_KIMI_BIN:-$HOME/.kimi-code/bin/kimi}"
CODER_HOME="${AMI_KIMI_CODER_HOME:-$HOME/.kimi-code-ami-coder}"

# The endpoint + the model root we REQUIRE to be behind it. Read from the registry so there is one
# source of truth for the URL, and pinned here for the identity.
VLLM_API=$(python3 -c "import json;print(json.load(open('$API_JSON'))['ami-vllm']['api'])")
MODEL_ID=$(python3 -c "import json;print(next(iter(json.load(open('$API_JSON'))['ami-vllm']['models'])))")
EXPECT_ROOT=/models/qwen38-flash-next-nvfp4

[ -x "$KIMI_BIN" ] || { echo "FATAL: kimi not executable at $KIMI_BIN (set AMI_KIMI_BIN)" >&2; exit 3; }
[ -f "$API_JSON" ] || { echo "FATAL: registry missing: $API_JSON" >&2; exit 2; }

# --- 1. Identity, read not assumed -------------------------------------------------------------
# CLAUDE.md: "the alias `ami-llm` was reused across the 2026-08-28 swap — never identify the model
# by that name, always read `root` from /v1/models". A serve answering on the right port with the
# wrong weights behind it is the failure this catches.
echo "==> probing $VLLM_API/models"
ROOT=$(curl -s -m 10 "$VLLM_API/models" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);r={m.get('root') for m in d.get('data',[])};print(sorted(r)[0] if len(r)==1 else 'AMBIGUOUS:'+repr(sorted(r)))" 2>/dev/null) \
  || { echo "FATAL: vLLM unreachable at $VLLM_API — foreign coder tier is UNAVAILABLE, not 'clean'." >&2; exit 3; }
[ "$ROOT" = "$EXPECT_ROOT" ] || {
  echo "FATAL: model identity mismatch. expected root=$EXPECT_ROOT, serve reports: $ROOT" >&2
  echo "       Refusing to register — a renamed alias in front of different weights is DEF059's shape." >&2
  exit 3; }
echo "    root=$ROOT  OK"

# --- 2. Serve the registry (kimi provider add rejects file:// — verified 2026-09-01) ------------
PORT=8791
while nc -z 127.0.0.1 "$PORT" 2>/dev/null; do PORT=$((PORT + 1)); done
SERVE_DIR=$(mktemp -d)
cp "$API_JSON" "$SERVE_DIR/api.json"
( cd "$SERVE_DIR" && exec python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 ) &
SRV_PID=$!
trap 'kill "$SRV_PID" 2>/dev/null || true; rm -rf "$SERVE_DIR"' EXIT INT TERM
curl -s --retry 20 --retry-delay 1 --retry-connrefused -o /dev/null "http://127.0.0.1:$PORT/api.json" \
  || { echo "FATAL: local registry server never came up on $PORT" >&2; exit 3; }

# --- 3. Import into the CODER home only --------------------------------------------------------
mkdir -p "$CODER_HOME"
echo "==> importing into KIMI_CODE_HOME=$CODER_HOME"
KIMI_CODE_HOME="$CODER_HOME" "$KIMI_BIN" provider add "http://127.0.0.1:$PORT/api.json" --api-key none

CFG="$CODER_HOME/config.toml"
[ -f "$CFG" ] || { echo "FATAL: provider add wrote no config at $CFG" >&2; exit 3; }
# `-p` needs a default_model; the import does not set one.
if grep -q '^default_model' "$CFG"; then
  python3 - "$CFG" "$MODEL_ID" <<'PY'
import re, sys
p, m = sys.argv[1], sys.argv[2]
s = open(p).read()
open(p, "w").write(re.sub(r'^default_model.*$', f'default_model = "ami-vllm/{m}"', s, count=1, flags=re.M))
PY
else
  printf 'default_model = "ami-vllm/%s"\n%s' "$MODEL_ID" "$(cat "$CFG")" > "$CFG.tmp" && mv "$CFG.tmp" "$CFG"
fi

# --- 4. Prove it, do not assume it -------------------------------------------------------------
echo "==> round-trip"
OUT=$(cd "$HERE" && KIMI_CODE_HOME="$CODER_HOME" "$KIMI_BIN" -p "Reply with exactly the single word READY and nothing else." 2>&1) || true
case "$OUT" in
  *READY*) echo "    round-trip OK" ;;
  *) echo "FATAL: round-trip failed. Output was:" >&2; echo "$OUT" >&2; exit 3 ;;
esac

echo
echo "registered: ami-vllm/$MODEL_ID  root=$ROOT"
echo "coder home: $CODER_HOME   (auditor keeps the default ~/.kimi-code — do not merge them)"
