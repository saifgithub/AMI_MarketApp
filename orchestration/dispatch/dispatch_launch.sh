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
  echo "usage: dispatch_launch.sh <instance-id> <lane> <tier:economy|standard|premium> <fanout:solo|ultra> \"<task body>\"" >&2
  exit 2
fi
INSTANCE=$1; LANE=$2; TIER=$3; FANOUT=$4; shift 4; BODY=$*

case "$TIER" in
  economy)  MODEL="claude-haiku-4-5-20251001"; EFFORT="low";    BUDGET=2 ;;
  standard) MODEL="claude-sonnet-5";           EFFORT="medium"; BUDGET=5 ;;
  premium)  MODEL="claude-opus-4-8";           EFFORT="high";   BUDGET=10 ;;
  *) echo "tier must be economy|standard|premium (got: '$TIER')" >&2; exit 2 ;;
esac

BASE_TOOLS="Bash Edit Write Read Grep Glob TodoWrite"
case "$FANOUT" in
  solo)  TOOLS="$BASE_TOOLS"; ULTRA_CLAUSE="" ;;
  ultra) TOOLS="$BASE_TOOLS Workflow Agent TaskOutput TaskStop"; BUDGET=$((BUDGET * 3))
         ULTRA_CLAUSE=" ULTRACODE ENABLED: for this heavy lane you MAY use the Workflow tool (ultracode) and the Agent tool to fan out parallel sub-agents INSIDE your own worktree. Keep each sub-agent at the cheapest tier its sub-task needs; your whole session (you + every fanned agent) shares one hard \$$BUDGET budget cap. The fan-out is disposable — land the result as ONE lane with one hand-off signal; the lane stays interrogable via your session." ;;
  *) echo "fanout must be solo|ultra (got: '$FANOUT')" >&2; exit 2 ;;
esac

SID=$(uuidgen | tr '[:upper:]' '[:lower:]')
PROMPT="AMI-TRADE · $INSTANCE · $LANE — ${BODY}${ULTRA_CLAUSE}"

# Record the live handle in a PER-LANE file so the worker is interrogable (CR061). Writing the
# shared roster/<instance>.md (old behaviour) collided under same-instance concurrency and left it
# modified-uncommitted every launch; a disjoint per-lane handle file avoids both. Non-fatal.
HANDLES="$REPO/orchestration/dispatch/handles"
mkdir -p "$HANDLES" 2>/dev/null || true
printf '%s\t%s\t%s/%s\t$%s cap\tclaude --resume %s\n' "$SID" "$INSTANCE" "$TIER" "$FANOUT" "$BUDGET" "$SID" \
  > "$HANDLES/$LANE.handle" 2>/dev/null || echo "warn: handle file not written for $LANE" >&2

echo "launch  $INSTANCE  lane=$LANE  tier=$TIER($MODEL/$EFFORT)  fanout=$FANOUT  budget=\$$BUDGET  session=$SID"
echo "resume  claude --resume $SID"

cd "$REPO" || { echo "cannot cd $REPO" >&2; exit 1; }

# DISPATCH_DRY_RUN=1 prints the resolved launch (for verification / review) and exits without
# spending a worker or touching the roster's meaning — the exec line is the single source of truth.
if [ "${DISPATCH_DRY_RUN:-0}" = "1" ]; then
  echo "DRY-RUN — would exec:"
  echo "claude -p --permission-mode acceptEdits --allowedTools \"$TOOLS\" --add-dir \"$REPO\" --model $MODEL --effort $EFFORT --max-budget-usd $BUDGET --session-id $SID \"<prompt: ${#PROMPT} chars>\""
  exit 0
fi

exec claude -p --permission-mode acceptEdits \
  --allowedTools "$TOOLS" \
  --add-dir "$REPO" \
  --model "$MODEL" --effort "$EFFORT" --max-budget-usd "$BUDGET" \
  --session-id "$SID" \
  "$PROMPT"
