<!-- auditor lane — track U (Kimi). CR052 / orchestration/audit/PROTOCOL.md. -->
# REL61 — auditor

VERDICT: COMPLETE (round 1)

SCOPE: `release-bundle`. Audited merged `main` @ `06e12ba1` in scratch
worktree `.claude/worktrees/audit-REL61` (contains BE1 `8a056ba3`, BE2
`6717d065`, MOBILE `cf1de0ea`). Per the bridge's instruction I did NOT re-run
the full suites (architect reproduced 1645/330); the round went to the seams
— per-field five-layer traces, three probes, one mutation re-check, one live
measurement.

---

## Round 1 — the trace, per field

Method: one probe (`/tmp/rel61_trace.py`) driving the real floor resolvers and
the real overlay generator for a fully-SET user and a fully-UNSET user, a
`_deep_merge` sibling-stability probe, a consumer census (grep, whole
`backend/app`), targeted lane tests on merged main (52 backend + 21 mobile),
and a live OpenAPI read of Alpha.

| Field | UI | PATCH | Store | Floor (ticket + Room) | Overlay | Verdict |
|---|---|---|---|---|---|---|
| `sector_cap_pct` | value / "Following your risk profile" | explicit-null-safe | merge-stable | explicit, else preset 0.4 | **same number** (33.0% set / 40.0% unset) | ✅ all layers agree |
| `single_name_cap_pct` | same | same | same | explicit, else **50.0%** | explicit, else **3.0%** | ✅ set / ⚠ unset = DEF187 (minted) |
| `post_loss_cooldown_hours` | value / "OFF" | `"key" in updates` | plain field | set → both paths (r2-wired); unset → off | 48.0h / "not set" | ✅ |
| `max_open_positions` | same | same | same | same | 7 / "not set" | ✅ |
| `max_trades_per_day` | same | same | same | same | 3 / "not set" | ✅ |
| `max_trades_per_week` | same | same | same | same | 9 / "not set" | ✅ |
| `max_open_risk_pct` | same | same | same | same | 2.5% / "not set" | ✅ |

For a SET user every layer speaks the user's own number, measured: floor
resolvers returned `17.0` / `0.33`, the overlay narrated `17.0%`, `33.0%`,
`48.0h`, `7`, `3 / 9`, `2.5%` — interpolated, no literal, matching the UI's
source values exactly. For an UNSET user the only numeric divergence at any
layer is `single_name_cap_pct` (floor 50.0% vs overlay/PM-prompt 3.0%,
~16.7x) — that is **DEF187, already minted**, measured here with concrete
numbers, not restated as new. The BE1-unset-vs-BE2-unset UI distinction
("Following your risk profile" vs "OFF") is correct at every layer: BE1's
two bind via preset, BE2's five are genuinely unenforced, and the overlay
says exactly that.

## The five attacks, answered

1. **Unset user.** Correct everywhere except the minted DEF187/DEF193 pair.
   Overlay narrates the sector preset the floor actually applies (40.0% =
   0.4, same table). For single-name it narrates the risk-tier preset the
   floor does NOT apply (DEF187).
2. **Sibling stability.** Probe: a one-field PATCH moved **none** of the
   other six; explicit `null` and explicit `0` both survive `_deep_merge`;
   persist re-validates through the full `Mandate` schema (DEF062). ✅
3. **Third consumer.** Census of all 9 files touching the seven fields: the
   consumers beyond floor + overlay are `room_prompts.py:420` (PM prompt
   clamp — `resolved_single_name_cap_pct`, the DEF187 participant),
   `sector_allocation.py:151-156` (the floor's own sector resolver), and the
   `sizing.py` preset tables. None unaccounted for. The BE2-r2 AST guard
   covers `check_mandate_compliance` callees; the `enforce_safety_floor`
   live-PM site (my BE2 M4) is now pinned by assertion — **I re-ran my
   mutation MA against merged main: kwargs dropped at the live-PM site →
   exactly 1 RED** (`test_room_live_pm_enforce_safety_floor_rejects_a_post_loss_cooldown_approve`,
   which now asserts "active until" present AND "did not supply" absent).
   Reverted, tree clean. M4 closed for real.
4. **Overlay vs UI numeric agreement.** Set users: identical source, no
   divergence. Unset BE1: UI shows no number (DEF193, minted), overlay shows
   the resolved preset — asymmetric but honest, not contradictory.
5. **0 vs null.** Traced the whole chain: Dart parses `(j as num?)?.toInt()`
   (null-safe, no `?? 0`), dio serializes explicit nulls, server uses
   `"key" in updates`, `_deep_merge` preserves both, floor checks
   `is not None`, overlay checks `is None`. No falsy coercion anywhere.
   Observation: `0` binds as "block everything" on six of seven fields but
   is a no-op on `post_loss_cooldown_hours` (a zero-hour wait) — domain-
   sensible, recorded as MINOR r3 for the doc, not a defect.

## Live measurement

Alpha (`api-alpha.agenticmarketintel.ai`): caught mid-restart (502, container
"Up 3 minutes (healthy)" by the time I checked melehost), then my own
OpenAPI read confirmed **all seven fields present** in the live `Mandate`
schema — the architect's "all seven read LIVE" claim independently
reproduced.

## The architect's invited opinion — the deployment-order gate

Yes, that is a real hole, and the bundle already proved it: `0.1.0+61` was
uploading while Alpha's schema lacked all seven fields, and `extra='ignore'`
guaranteed a 200-and-drop — a control that looks authoritative and writes
nothing, DEF129 reintroduced by deploy ORDER. `infra/PROMOTION_HOLD.md`
covers backend-ready/client-not-shipped; nothing covers client-shipped/
backend-behind. Agree it wants minting — a promotion-order gate (client
release must not ship keys the live backend doesn't accept) with the check
mechanical (OpenAPI diff vs the client's PATCH key set), not procedural.

## MINORs (new, recorded, not blocking)

- r1. Unset BE2 overlay lines read self-contradictory to an LLM reader:
  `Post-loss cooldown: not set (no cooldown enforced) — enforced as a hard
  block on the next BUY, not a suggestion.` The static mechanism suffix
  attaches to the "not set" state. Cosmetic prompt wart; the PM sees it on
  every unset user (the majority today). Suggest suppressing the suffix when
  the field is unset. Architect's call.
- r2. The mandate-edit journal doesn't narrate the two BE1 caps — the BE2
  five got per-field diff lines (`api/mandate.py:110-124`), the BE1 two
  didn't, so PATCHing `sector_cap_pct` journals the bare "Mandate updated."
  Cosmetic asymmetry in the audit trail the user reads.
- r3. `0` semantics note (above): block-everything on six fields, no-op on
  cooldown. Worth one doc line, not code.

## Builder disclosures (bridge §"accepted by me, open to challenge")

All four re-weighed against measurements from my own lane audits and this
round's probes: BE1's kept 50% fallback (measured 43-RED tightening — upheld
at `9608d56d`), BE2's UTC basis + per-row risk pricing (upheld at
`050dc32c`), MOBILE's post-save audit + no-number rendering (upheld at
`5435ac46`). Nothing new surfaced to overturn any of them.

Zero BLOCKER + zero MAJOR → **COMPLETE**. The bundle's product claim — a
number the user sets is the number that binds — holds at every layer for set
users, and the two unset-user divergences are minted, measured, and open,
not silent.
