#!/bin/sh
# dispatch_launch.sh — one-command headless launch of a fleet instance (CR057).
#
# WHY: workers were hand-assembled and six footguns each cost time; one (a silent premium model
# at max effort, no budget cap) cost money. This encodes THE working recipe once, makes the cost
# TIER a required deliberate choice (heritage MABP §15: name the tier, not the model), fences every
# worker with a HARD dollar cap, and can grant ultracode fan-out to heavy lanes.
#
# USAGE (the CALLER runs this via the Bash tool with run_in_background:true so the worker is
# task-tracked — that exit callback is what the liveness rule keys on; this script never self-bg's):
#
#   sh orchestration/dispatch/dispatch_launch.sh <instance-id> <lane> <tier> <fanout> "<task body>"
#
#   <tier>   economy | standard | premium   (capability level — MABP §15 abstraction)
#   <fanout> solo | ultra                    (ultra = grant Workflow+Agent tools + the ultracode
#                                             clause so a heavy lane may fan out INSIDE its worktree)
#   <task body> = the prompt BODY only; the script prepends the readable title
#                 "AMI-TRADE · <instance> · <lane> — " so `claude --resume` shows a legible name.
#
# TIER RESOLUTION (mirror of the DoD "Model/effort/budget" row + BINDINGS tier table).
# START CHEAP, ESCALATE ON FAILURE (MABP §15 ladder): economy fail → relaunch standard (never retry
# economy); standard → standard(once) → premium → BLOCKER; an EXTERNAL/harness failure (a died
# worker, infra) is a BLOCKER at 0 retries — it never earns a premium retry.
#   economy   claude-haiku-4-5-20251001  low     mechanical/deterministic (finish, wiring, commit)
#   standard  claude-sonnet-5            medium  implementation + content authoring; then reviewed
#   premium   claude-opus-4-8            high    guard/schema/safety logic + the auditor gate
# <fanout>=ultra triples the budget (fan-out needs headroom) and adds the ultracode tools.
#
# HARD RULES baked in (each learned the hard way — see failure_patterns.md P6/P7):
#   * a SIMPLE `claude -p …` (matches the Bash(claude -p *) allow rule).
#   * NO --dangerously-skip-permissions (the classifier hard-blocks it categorically).
#   * NO output redirect / trailing & (compound => allow-rule miss => blocked; & also detaches the
#     worker from task-tracking, killing the completion callback the liveness rule needs).
#   * a SCALAR flag (--session-id) sits IMMEDIATELY before the prompt: --add-dir AND --tools are
#     variadic and will EAT a trailing prompt (silent: "Input must be provided…", no session).
#   * model + effort + a HARD --max-budget-usd are always set — no silent premium/uncapped default.

set -u
REPO="/Volumes/Extreme Pro/AMI_MarketApp"

if [ $# -lt 5 ]; then
  echo "usage: dispatch_launch.sh <instance-id> <lane> <tier:local|economy|standard|premium> <fanout:solo|ultra> \"<task body>\"" >&2
  exit 2
fi
INSTANCE=$1; LANE=$2; TIER=$3; FANOUT=$4; shift 4; BODY=$*

# `local` (CR215) is a FOREIGN harness, not a Claude model: Qwen3.8-Flash-Next on the on-prem vLLM,
# driven by Kimi Code against its own config home. It sits BELOW economy on the ladder — free (local
# GPU), so it costs nothing to try first, and `local` fail -> standard, never retry the same tier.
HARNESS=claude
case "$TIER" in
  local)    HARNESS=kimi; MODEL="ami-vllm/qwen3.8-flash-next"; BUDGET=0 ;;
  economy)  MODEL="claude-haiku-4-5-20251001"; EFFORT="low";    BUDGET=2 ;;
  standard) MODEL="claude-sonnet-5";           EFFORT="medium"; BUDGET=5 ;;
  premium)  MODEL="claude-opus-4-8";           EFFORT="high";   BUDGET=10 ;;
  *) echo "tier must be local|economy|standard|premium (got: '$TIER')" >&2; exit 2 ;;
esac

if [ "$HARNESS" = "kimi" ]; then
  # NEVER a cheap gate. BINDINGS.md:73 "Never economy tier for an auditor", and DEF059 is what a
  # gate that can fail open actually costs: LLM down -> confident fake APPROVE -> shipped. `local`
  # is a BUILD tier only; the foreign AUDIT path is dispatch_foreign_audit.sh, on a different family.
  case "$INSTANCE" in
    *auditor*|*audit*) echo "refusing TIER=local for auditor-shaped instance '$INSTANCE' — local is a build tier only (CR215)" >&2; exit 2 ;;
  esac
  # kimi has no Workflow/Agent tools, so `ultra` cannot mean anything here. Failing loud beats
  # silently handing back a solo worker the caller believes is fanned out.
  [ "$FANOUT" = "ultra" ] && { echo "fanout=ultra is not available on TIER=local (kimi has no Workflow/Agent tools)" >&2; exit 2; }
  KIMI_BIN="${AMI_KIMI_BIN:-$HOME/.kimi-code/bin/kimi}"
  KIMI_HOME="${AMI_KIMI_CODER_HOME:-$HOME/.kimi-code-ami-coder}"
  [ -x "$KIMI_BIN" ] || { echo "TIER=local UNAVAILABLE: no kimi at $KIMI_BIN" >&2; exit 3; }
  [ -f "$KIMI_HOME/config.toml" ] || { echo "TIER=local UNAVAILABLE: coder home not registered at $KIMI_HOME — run orchestration/harness/register_ami_vllm.sh" >&2; exit 3; }
fi

# BUDGET OVERRIDE — size the cap to the LANE, not just to the tier.
# Budget used to be derived from tier alone, so the only way to buy more headroom was to buy a
# bigger model (or `ultra`, which also switches on fan-out tooling nobody asked for). That coupling
# is what killed CR098-ROOM twice on 2026-07-27: a 277-line spec with 14 acceptance criteria was
# dispatched at standard's $5 because $5 is what standard means. Capability was never the problem.
# Rule of thumb from that lane: ~$1 per acceptance criterion, floor $5. If a lane needs much more
# than $15, that is the decomposition telling you it is really two lanes.
if [ -n "${DISPATCH_BUDGET_USD:-}" ]; then
  case "$DISPATCH_BUDGET_USD" in
    ''|*[!0-9]*) echo "DISPATCH_BUDGET_USD must be a positive integer (got: '$DISPATCH_BUDGET_USD')" >&2; exit 2 ;;
  esac
  [ "$DISPATCH_BUDGET_USD" -gt 0 ] || { echo "DISPATCH_BUDGET_USD must be > 0" >&2; exit 2; }
  BUDGET="$DISPATCH_BUDGET_USD"
fi

BASE_TOOLS="Bash Edit Write Read Grep Glob TodoWrite"
case "$FANOUT" in
  solo)  TOOLS="$BASE_TOOLS"; ULTRA_CLAUSE="" ;;
  ultra) TOOLS="$BASE_TOOLS Workflow Agent TaskOutput TaskStop"; BUDGET=$((BUDGET * 3))
         ULTRA_CLAUSE=" ULTRACODE ENABLED: for this heavy lane you MAY use the Workflow tool (ultracode) and the Agent tool to fan out parallel sub-agents INSIDE your own worktree. Keep each sub-agent at the cheapest tier its sub-task needs; your whole session (you + every fanned agent) shares one hard \$$BUDGET budget cap. The fan-out is disposable — land the result as ONE lane with one hand-off signal; the lane stays interrogable via your session." ;;
  *) echo "fanout must be solo|ultra (got: '$FANOUT')" >&2; exit 2 ;;
esac

SID=$(uuidgen | tr '[:upper:]' '[:lower:]')

# FINISH-THE-TURN clause, appended to every launch. Measured 2026-07-30: three of four lanes in one
# wave (BE-AGENTS, BE-GUARD191, ROOM-DEF161) backgrounded the test suite, said "I'll pause here and
# wait for the background run to notify me", and ENDED THE TURN — which in `claude -p` terminates
# the process. All three left complete, correct, uncommitted work in their worktrees and no hand-off,
# and the Architect had to verify and land it by hand. This is the same shape as the budget-cap
# death (work done, nothing delivered) but self-inflicted and entirely avoidable: a headless run has
# no next turn to be notified into. The rule is about the LAST step, not about backgrounding per se.
FINISH_CLAUSE=" HARD RULE — YOU ARE HEADLESS, THERE IS NO NEXT TURN: this is a \`claude -p\` run, so
when your turn ends the process exits. NEVER end your turn waiting to be notified about a background
job — no \"I'll pause here and pick up when the suite finishes\". If you background the test suite,
you MUST block until it completes (poll it in the foreground) and then finish the lane in the SAME
turn: commit, push your lane branch, and write the hand-off file. Three lanes were lost to exactly
this on 2026-07-30, each with correct work already written and nothing delivered. Write the hand-off
file EARLY and update it as you go, so that even a hard stop leaves your account behind."

PROMPT="AMI-TRADE · $INSTANCE · $LANE — ${BODY}${ULTRA_CLAUSE}${FINISH_CLAUSE}"

# Record the live handle in a PER-LANE file so the worker is interrogable (CR061). Writing the
# shared roster/<instance>.md (old behaviour) collided under same-instance concurrency and left it
# modified-uncommitted every launch; a disjoint per-lane handle file avoids both. Non-fatal.
HANDLES="$REPO/orchestration/dispatch/handles"
mkdir -p "$HANDLES" 2>/dev/null || true
if [ "$HARNESS" = "kimi" ]; then
  # kimi mints its own session id and prints it on exit, so there is no id to pre-record here.
  printf '%s\t%s\t%s/%s\tfree\tkimi -r <id printed at exit>\n' "$MODEL" "$INSTANCE" "$TIER" "$FANOUT" \
    > "$HANDLES/$LANE.handle" 2>/dev/null || echo "warn: handle file not written for $LANE" >&2
else
  printf '%s\t%s\t%s/%s\t$%s cap\tclaude --resume %s\n' "$SID" "$INSTANCE" "$TIER" "$FANOUT" "$BUDGET" "$SID" \
    > "$HANDLES/$LANE.handle" 2>/dev/null || echo "warn: handle file not written for $LANE" >&2
fi

if [ "$HARNESS" = "kimi" ]; then
  echo "launch  $INSTANCE  lane=$LANE  tier=$TIER($MODEL)  fanout=$FANOUT  budget=free(local GPU)"
  echo "resume  kimi -r <session id printed when the run ends>"
else
  echo "launch  $INSTANCE  lane=$LANE  tier=$TIER($MODEL/$EFFORT)  fanout=$FANOUT  budget=\$$BUDGET  session=$SID"
  echo "resume  claude --resume $SID"
fi

cd "$REPO" || { echo "cannot cd $REPO" >&2; exit 1; }

# DISPATCH_DRY_RUN=1 prints the resolved launch (for verification / review) and exits without
# spending a worker or touching the roster's meaning — the exec line is the single source of truth.
if [ "${DISPATCH_DRY_RUN:-0}" = "1" ]; then
  echo "DRY-RUN — would exec:"
  if [ "$HARNESS" = "kimi" ]; then
    echo "KIMI_CODE_HOME=$KIMI_HOME $KIMI_BIN -p \"<prompt: ${#PROMPT} chars>\" -m $MODEL"
  else
    echo "claude -p --permission-mode acceptEdits --allowedTools \"$TOOLS\" --add-dir \"$REPO\" --model $MODEL --effort $EFFORT --max-budget-usd $BUDGET --session-id $SID \"<prompt: ${#PROMPT} chars>\""
  fi
  exit 0
fi

if [ "$HARNESS" = "kimi" ]; then
  # Pre-register the run: a `local` lane that dies must still be visible in the ledger, because
  # exec replaces this process and nothing here runs afterwards to record it (MHBP 9/10).
  printf '| %s | %s | — | — | coder | %s | — | lane %s launched |\n' \
    "$(date -u +%Y-%m-%d)" "$LANE" "$MODEL" "$LANE" >> "$REPO/orchestration/audit/foreign_trail.md" 2>/dev/null || true
  # No --session-id (kimi mints its own), no --max-budget-usd (local GPU is free), no
  # --permission-mode (verified 2026-09-01: `-p` rejects both --auto and --yolo, and uses tools
  # under default permissions anyway). The watchdog is here because `kimi -p` does not reliably
  # exit once the model has stopped working.
  exec env KIMI_CODE_HOME="$KIMI_HOME" python3 "$REPO/orchestration/harness/run_timeout.py" \
    "${LOCAL_TIMEOUT_S:-1800}" "$KIMI_BIN" -p "$PROMPT" -m "$MODEL"
fi

exec claude -p --permission-mode acceptEdits \
  --allowedTools "$TOOLS" \
  --add-dir "$REPO" \
  --model "$MODEL" --effort "$EFFORT" --max-budget-usd "$BUDGET" \
  --session-id "$SID" \
  "$PROMPT"
