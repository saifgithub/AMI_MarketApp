<!--
DEF419-BE.architect.md — audit lane. State derives from round numbers here vs DEF419-BE.auditor.md.
GATE: independent (CR231 / D-072). It touches the safety-floor input path, so it is Tier A.
-->

# DEF419-BE — audit lane (per-account mandate check on /v1/sim/preview)

**SCOPE:** chunk (the backend half; the mobile half follows as DEF419-MOBILE)

**TIER: A.** This changes what `check_mandate_compliance` sizes against: it swaps in a different denominator and holdings set.

**SHA:** `b945142c` (fix) + `942b937b` (merge of `main`; the only conflict was the generated register, which I regenerated). Both are on `main`. Review with `git diff 4fb4f02f..b945142c`.

**depends-on:** none. **Promoted:** no. It needs `/promote-to-alpha` after this verdict, and the mobile half is useless without it.

## What and why
Saiful, 2026-09-24, from TestFlight +108 screenshots (ASML, buy 10 @ $1731, destination ALPACA PAPER → "position size 137.2% exceeds single-name cap 100.0%"):

> *"When placing an order either for both or for alpaca paper only, the mandate is checked against the local AMI SIM account. The mandate should check limits based on the account in use. It does mean that it may reject for ami and approve for alpaca. Or vice versa. This is an expected condition."*

**The fix:**
- `SubmitTradeRequest.account: AccountSnapshotIn | None` is read by the **preview** endpoint only.
- When present, `SimEngine.preview` runs the SAME `check_mandate_compliance`, with the SAME mandate, against the snapshot's equity, cash and positions.
- When absent, behaviour is byte-identical to before.
- Submit ignores the snapshot, so an AMI fill can never be sized against a foreign account.
- The response echoes `account_kind`.

Design note, including the per-account / per-user / mandate-level rule table: `docs/defect/DEF419_per_account_mandate_check.md`.

## Tests (Architect re-ran on the merged tree, bare)
`cd backend && .venv/bin/python -m pytest tests/unit/test_def419_per_account_mandate_check.py tests/unit/test_safety_floor.py tests/unit/test_sim_engine.py tests/unit/test_p30_registers_name_things_that_exist.py tests/unit/test_config_compose_parity.py -q -p no:cacheprovider` → `71 passed, 1 skipped` (exit 0).

The builder also ran `-k "sim or alpaca or safety_floor or preview or mandate or account"` → 403 passed. That is not the full suite: the shared Mac is overloaded, and the auditor's run on melehost is the authoritative one.

## Measurement
None live yet. The reproduction for the auditor on Alpha after promotion:
- Preview the ASML ×10 order with a $100k `alpaca_paper` snapshot. It should be accepted.
- Preview the same order without the snapshot. It should be rejected at about 137%.

## Attack surface (please probe)
1. **Client-attested snapshot (known limit, CR202 custody):** the server cannot verify the Alpaca figures. Judge whether validation is tight enough: the finite, bounded, `extra=forbid` and ticker-pattern checks. Judge whether "the user lies about their own paper account" is acceptable for a paper-only mandate (D-071).
2. **Drawdown is set to `0.0` on the snapshot path:** the drawdown rule can never fire for Alpaca. Is that silent (the CR040 degrade-loudly question)? Should the preview surface "drawdown not measurable for this account" instead?
3. **Shorts are ignored:** `sizing_shorts=None`, and negative quantities in the snapshot produce `avg_cost` 0 and are dropped from quotes. Does a short Alpaca position escape the long_only and gross-exposure checks?
4. **Per-user limits read the AMI ledger:** the total open-risk cap, trade counts and cooldown all come from AMI's own history. Is sizing open risk on AMI's ledger right when the order goes to Alpaca?
5. **Bypass:** can a preview with the snapshot be replayed into `submit` so an AMI fill is sized against the foreign equity? The builder says submit ignores the field.
6. **No persistence:** the preview must still perform zero DB writes. There is a dedicated guard test.

SUBMITTED: round 1
