<!--
DEF419-MOBILE.architect.md — audit lane. State derives from round numbers here vs DEF419-MOBILE.auditor.md.
GATE: independent (CR231 / D-072). It touches the safety-floor input path on the client side (which account gets checked, and what happens when that check can't be fetched), so it is Tier A.
-->

# DEF419-MOBILE — audit lane (per-account mandate check, mobile half)

**SCOPE:** chunk (the mobile half; depends on the backend half, DEF419-BE)

**TIER: A.** This decides which account's snapshot reaches `/v1/sim/preview`, and what the ticket does when that snapshot can't be fetched. Get either wrong and a trade either checks against the wrong account again (this DEF's own bug, recurring) or silently degrades past the mandate floor.

**SHA:** `f2bc07b9` (mobile fix, this session). Backend half is `b945142c` (already on `main`, awaiting DEF419-BE audit). Review with `git diff b945142c..f2bc07b9`.

**depends-on:** DEF419-BE (backend schema/route/engine change this relies on to exist). **Promoted:** no. `/promote-to-alpha` covers the backend half only until this half is also promoted — the mobile build itself ships separately (TestFlight/Play), not via `/promote-to-alpha`.

## What and why

Saiful, 2026-09-24, from the same TestFlight screenshot DEF419-BE was filed from (ASML buy 10 @ $1731, destination ALPACA PAPER → "position size 137.2% exceeds single-name cap 100.0%"):

> *"When placing an order either for both or for alpaca paper only, the mandate is checked against the local AMI SIM account. The mandate should check limits based on the account in use. It does mean that it may reject for ami and approve for alpaca. Or vice versa. This is an expected condition."*

DEF419-BE made `/v1/sim/preview` able to check against a supplied account snapshot instead of AMI's own portfolio. Nothing on the client actually supplied one — `_submitAlpacaOnly` still called `preview()` with no `account`, so the backend fix was inert until this half wired it up.

**The fix:**
- `TradeTicketSheet._fetchAlpacaSnapshot()` fetches the linked Alpaca account (`AlpacaClient.account()` + `.positions()`), cached per ticket session with a 30s TTL, shared across concurrent callers via a `Completer`.
- `_submitAlpacaOnly` (ALPACA PAPER) fetches the snapshot, serializes it via `AlpacaSnapshot.toMandateSnapshotJson()` (the `AccountSnapshotIn` wire shape: `kind`/`equity`/`cash`/`positions[{ticker,qty,market_value}]` — deliberately a **different** method from the existing `toWireJson()`, which serializes the unrelated Room-overlay `AlpacaSnapshotIn` shape for a different endpoint), and passes it as `preview(...).account`.
- On a fetch failure, the ticket shows "Couldn't read your Alpaca paper account — order not sent" and sends nothing. It never falls back to previewing (or submitting) against AMI.
- BOTH (`_submitBoth`) now runs `_legAmi` (ordinary `submit()`, checked against AMI) and `_legAlpaca` (snapshot-sized preview + place) via `Future.wait`, with **neither gating the other**. Before this fix, the AMI leg's own accept/reject gated whether the Alpaca leg ran at all.
- The legacy single-verdict "SAFETY FLOOR — TRADE BLOCKED" refusal panel (driven by `state.lastSubmit`) is suppressed whenever the per-destination outcomes panel (`_destinationOutcomes`) is populated, so a BOTH call with a mixed outcome doesn't render the AMI violation sentence twice (once unlabelled at the top, once under "AMI SIM" in the outcomes panel).
- `SimNotifier.preview` / `ApiClient.simPreview` gain an optional `account` map parameter, forwarded as-is to the wire. `SimPreviewResult.accountKind` echoes the backend's `account_kind`.

Design note (mobile follow-up spec, written by DEF419-BE): `docs/defect/DEF419_per_account_mandate_check.md`'s "Mobile follow-up" section.

## Tests (Architect ran on this tree, bare)

```
cd mobile && flutter test
```
→ **1505 passed** (exit 0). Includes the 6 new `def419_per_account_test.dart` cases (snapshot used on ALPACA PAPER and never calls AMI's own submit; the DEF's own repro — AMI rejects the ASML-shaped order at ~137%, Alpaca accepts the same order against a larger account; Alpaca fetch failure on ALPACA PAPER and on BOTH, with the AMI leg still running independently in the BOTH case; BOTH with AMI-reject/Alpaca-accept and the reverse direction) plus the updated `cr227_destination_routing_test.dart` (6) and `cr230_alpaca_order_log_test.dart` (12) fixtures, which needed `account()`/`positions()` stubs added to their Alpaca-client test doubles now that `_submitAlpacaOnly` fetches the account before previewing.

```
cd mobile && flutter analyze
```
→ **11 issues, 0 errors** — matches the pre-change baseline exactly (verified by running `flutter analyze` before making any change). None of the 11 are new; all are pre-existing `info`-level items unrelated to this DEF (deprecated `copyWith`, `use_build_context_synchronously`, `use_super_parameters`, `unnecessary_import`, deprecated `hasFlag`).

## Measurement

None live yet — this hasn't shipped to a device build. The reproduction for the auditor, once both halves are promoted/built:
1. Link an Alpaca paper account sized larger than $10k (e.g. $100k).
2. Convene/open a ticket for a trade sized to breach AMI's $10k single-name cap but clear the Alpaca account's cap (the ASML-shaped repro).
3. Pick ALPACA PAPER. Expect: accepted, order placed on Alpaca.
4. Same ticket, pick AMI SIM. Expect: rejected, ~137%-style violation.
5. Pick BOTH. Expect: AMI SIM shown rejected, ALPACA PAPER shown accepted and placed — both in the same result panel, neither blocking the other.
6. Revoke/clear the Alpaca credential, then attempt ALPACA PAPER. Expect: "Couldn't read your Alpaca paper account — order not sent", no Alpaca order, no fallback AMI-sized preview.

## Attack surface (please probe)

1. **Cache staleness (new in this half):** the Alpaca snapshot is cached 30s per ticket session. If the user's Alpaca positions/equity change mid-session (e.g. another device places a trade, or a fill settles) within that window, the mandate check reads a stale snapshot. Judge whether 30s is tight enough for a paper account where the stakes are simulated, or whether it should be shorter / invalidated on specific triggers.
2. **Concurrent-fetch fix (the bug found during this session's own testing):** the original `_fetchAlpacaSnapshot` returned the same in-flight `Future` to both BOTH legs; a fetch failure with two listeners tripped Dart's unhandled-exception zone reporting under `flutter test` even though both callers `try/catch`'d it correctly. Fixed by routing every caller through its own `Completer.future`. Please verify this actually holds under a real fetch failure in BOTH (test: "BOTH: an unreadable Alpaca account still lets the AMI leg place independently") and isn't just quieted in the test harness specifically.
3. **Fetch-failure path — no AMI fallback:** confirm `_submitAlpacaOnly` and `_legAlpaca` truly send nothing when the Alpaca fetch throws — no preview call (with or without an account), no submit call. Grep for any path that could still reach `simNotifierProvider.preview()`/`.submit()` after a caught fetch exception.
4. **BOTH independence:** confirm `_legAmi` and `_legAlpaca` genuinely don't read each other's state before deciding to proceed — no shared mutable flag between them that a race could corrupt. `Future.wait` starts both eagerly; verify there's no accidental ordering dependency (e.g. `_legAlpaca` reading `state.lastSubmit`, which `_legAmi`'s `submit()` writes, before `_legAmi` has run).
5. **Refusal-panel suppression:** the legacy `refusal` panel is now gated on `_destinationOutcomes.isEmpty`. Confirm this doesn't accidentally suppress a genuine AMI-only-destination rejection (i.e. `_destinationOutcomes` should stay empty on the plain AMI Sim path, where the old single-verdict panel is still the only display and must still render).
6. **Position sign/short handling in `toMandateSnapshotJson()`:** negative-qty (short) Alpaca positions are dropped rather than sent negative, matching the backend's `AccountPositionIn.qty: ge=0` bound and the engine's `shorts=None` on the snapshot path (documented limitation, not new to this half). Confirm a short Alpaca position doesn't silently evade the long-only/gross-exposure checks by simply being absent from the snapshot the mandate sees.
7. **Wire-shape confusion:** `AlpacaSnapshot` now has two serializers — `toWireJson()` (Room-overlay `AlpacaSnapshotIn`) and `toMandateSnapshotJson()` (this DEF's `AccountSnapshotIn`). Confirm no call site was pointed at the wrong one (a mismatch would 422 immediately given both schemas' `extra="forbid"`, so this is a loud-not-silent risk, but worth a specific look).

SUBMITTED: round 1
