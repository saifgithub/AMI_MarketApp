# E5 — device-matrix runbook (cable install)

Part of [CR004](CR004_release_readiness.md). E5 is the **only** open item on the Engagement
close-out gate, and that gate is what holds Stealth Alpha recruitment at 10–20 personal invites
([CR036 §2](../CR036_go_to_market_plan/CR036_go_to_market_plan.md)). It has been open since
2026-07-25 for want of device time, not for want of a plan.

Saiful, 2026-08-21 daily check-in: **"I can connect the phones to the Mac."** So this runbook is
written for cable install off the Mac, not TestFlight round-trips. It exists so the pass is a
mechanical hour: install, walk the list, mark ✅/❌, done.

The pass checklist itself stays where it already lives —
[`build_verification_execution.md`](build_verification_execution.md) §A2 — plus the **delta list**
below, which covers what shipped after that checklist was written (2026-07-25). Drills are §A3 of
the same file.

---

## 0. Before you plug anything in

```bash
cd "/Volumes/Extreme Pro/AMI_MarketApp"
curl -s https://api-alpha.agenticmarketintel.ai/v1/health          # backend up
curl -s https://api-alpha.agenticmarketintel.ai/v1/llm/status      # vllm, not mock
git log --oneline -1                                                # note the sha in the log below
grep '^version:' mobile/pubspec.yaml                                # note the build number
```

If health or llm/status is wrong, stop and fix that first — a device pass against a degraded
backend measures nothing.

## 1. Install (release builds only — never debug on a real device)

| Device | Command |
|---|---|
| iPhone 13 (`TESTING IPHONE 13`) | `scripts/install_iphone.sh` |
| iPhone 17 | `scripts/install_iphone.sh <device-id>` (`flutter devices` for the id) |
| Galaxy Note FE — Android 9 floor | `scripts/install_android.sh ce10171a8017590d01` |
| Galaxy A17 | `scripts/install_android.sh R5CY91AY99Y` |

`scripts/install_android.sh --list` finds the serial of anything not in that table.

**Go off-LAN for the pass** — cellular or a non-home Wi-Fi. On the LAN the app can reach melehost
directly and you will not exercise the Cloudflare Tunnel path testers actually use.

## 2. Walk the list

Per device: §A2 in [`build_verification_execution.md`](build_verification_execution.md), then the
delta below. Mark ✅/❌. **File every ❌ from the device** (long-press the app-version chip) so it
lands in `bug_reports` with the build, platform and screenshot attached — that is the same pipe
`/bug-monitor` and `/fix-bugs` read.

### Delta since the §A2 checklist was written (2026-07-25)

```
[ ] Floor v0.2: the answer carousel — SIM PORTFOLIO, YOUR TEAM'S CALLS, SECTOR WATCH, and the
    unactioned-convene scorecard each render with real numbers, not placeholders
[ ] Tester inbox (CR102): bell shows unread count; open a message; reply; a high-priority
    message raises the toast. Send yourself one with `scripts/messages.sh`
[ ] Portfolio Health (CR136): findings render; the methodology disclosure card is READABLE
    (see known-open DEF340 below before filing)
[ ] Mandate screen (CR129): the 7 resolved limits render, server-sourced
[ ] Resting orders (CR187): place a limit that will not fill → the book states what happened
[ ] Trades list (CR120): SHOW ALL on a long history does not hang or truncate silently
[ ] Credits exhausted → the winzip 402 card: amber countdown, lessons CTA, AMI speaks at 0
[ ] Push: a real notification arrives and deep-links (Android channel was DEF333 — verify)
[ ] Games standings, if the dark-launch build exposes them (see DEF343 below)
```

**Out of scope for this pass — flagged off in Alpha:** the structured Risk Officer
(`ROOM_RISK_OFFICER_ENABLED`), AdMob (`ADMOB_MODE` empty), and CR172 options beyond what slice 1–2
exposes. Do not chase them; if one is visible on device, that is itself the defect.

### Known-open — do NOT re-file these

| ID | What you will see |
|---|---|
| DEF340 | Portfolio Health methodology card: light-gray text on light-blue, unreadable |
| DEF341 | Watchlist: `GOOGL` wraps mid-symbol onto two lines |
| DEF342 | Brief Your Agent proposal: accept/reject row hidden behind Android system nav |
| DEF343 | Games standings: a tie reads as "I'm last" — no tie marker |
| DEF344 | Upgrade tap crashes when RevenueCat is unconfigured (payments track is parked) |

Anything else is new — file it.

## 3. Drills (once, from the Mac — not per device)

§A3 of [`build_verification_execution.md`](build_verification_execution.md): LLM down, market data
down, backend restart mid-Room, tunnel down, bad bearer. Record each result inline in that file.

## 4. Close the gate

E5 closes when **every device in the matrix has a recorded pass** and every ❌ carries a
`bug:<short-id>`. Then, per [CR036 §2](../CR036_go_to_market_plan/CR036_go_to_market_plan.md), the
remaining two graduation conditions are: zero open bugs sustained through the invite window, and a
meaningful slice of the cohort hitting ≥1 Convene the Room per week. Only then does recruitment
widen past personal invites.

## Log

| Date | Device | Build | Result | Notes |
|---|---|---|---|---|
| | | | | |
