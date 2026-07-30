<!-- lane hand-off — coder.api. CR052. -->
# BE-DEF160 — hand-off (round 1)

STATUS: READY_FOR_AUDIT (round 1)
BRANCH: lane/BE-DEF160.coder.api (worktree `.claude/worktrees/coder.api-BE-DEF160`)

## What changed

Backend-only, per the fences. Two files touched, one test file added:

- `backend/app/schemas/onboarding.py` — `ReadbackConfirmRequest` gains
  `restart: bool = False`. Explicit, defaults off; a request that omits it
  is byte-for-byte the old contract.
- `backend/app/api/onboarding.py::confirm_readback` —
  - Gains `current_user: User | None = Depends(get_current_user_optional)`.
    Best-effort Bearer read, never required — anonymous callers get `None`
    and nothing about their path changes (acceptance 5).
  - After marking the session complete, if **both** `req.restart is True`
    **and** `current_user is not None`: builds the mandate from the
    completed session (`session_to_mandate_dict`) and calls
    `get_mandate_store().upsert(current_user.id, ...)` — replacing the
    stored mandate outright and bumping its version (store's existing
    version/upsert path, unmodified). `mandate_preview` in the response
    becomes the actually-applied mandate in this case.
  - Otherwise (the `else` branch, i.e. today's behaviour): same as before —
    builds a preview keyed to the sentinel `"anonymous-pending-claim"` and
    persists nothing. This covers both the plain anonymous path and an
    authenticated-but-not-restarting call (e.g. a stray Bearer token with no
    restart intent — deliberately inert, not just unauthenticated callers).
- `backend/app/api/auth.py` — **untouched**. DEF060's guard
  (`_bind_onboarding_session`, `get(user_id) is None` check, line 87) is
  exactly as it was. Verified by mutation test, see below.
- New test file: `backend/tests/unit/test_def160_restart_onboarding.py`
  (4 tests, all passing against the fix).

## Where the restart signal lives, and why it can't fire by accident

`restart` is a body field on `POST /v1/onboarding/readback/confirm`
(`ReadbackConfirmRequest.restart: bool = False`). It only does anything when
BOTH:
1. the request body sets it `true` (an omission or `false` is a no-op), AND
2. the caller sent a valid `Authorization: Bearer <token>` that resolves to
   a real user via `get_current_user_optional`.

Neither condition alone is enough — a client can't set it by forgetting a
default, and an unauthenticated client can't trigger it at all no matter
what it sends (see `test_restart_true_without_auth_does_not_persist_anything`).
This is why it's a genuinely separate operation from DEF060's bind guard
rather than a relaxed version of it: DEF060's path (`_bind_onboarding_session`)
never sees a `restart` flag and its `is None` check is completely unchanged.

## Anonymous path (acceptance 5)

`confirm_readback` uses `get_current_user_optional`, not `get_current_user`
— missing/invalid Bearer resolves to `current_user=None` instead of a 401.
The anonymous branch (`if req.confirm == "edit": ...` / the confirm path
with no restart) is textually identical to what shipped before this lane;
`test_readback_edit_returns_501_without_mutating_session` (pre-existing,
DEF048) and `test_restart_true_without_auth_does_not_persist_anything` (new)
both cover it green.

## Mandate version (acceptance 3)

No new versioning scheme — `MandateStore.upsert()` already increments
`version` on every write and keeps prior rows (`is_current` flips). Restart
goes through that same `upsert()`, so the bump and history are free;
`test_authenticated_restart_replaces_existing_mandate` asserts
`replaced.version == original_version + 1`.

## Mutation testing (acceptance 6) — done manually, not committed as a test

Both directions run and verified in this session (not left as permanent
code):

1. **Revert the fix**: `git stash push -- backend/app/api/onboarding.py
   backend/app/schemas/onboarding.py`, ran
   `test_def160_restart_onboarding.py` →
   `test_authenticated_restart_replaces_existing_mandate` went RED (asserts
   `halal is True`, got `False` — old code never touches the mandate store).
   Other 3 tests in the file stayed green (pydantic ignores the unknown
   `restart` field silently, which is itself informative: the field's
   presence alone is inert without the code path, consistent with "cannot
   be defaulted on"). Then `git stash pop` to restore.
2. **Remove the DEF060 guard the fix must NOT touch**: temporarily
   `sed`-patched `auth.py:87` from
   `if session.completed and get_mandate_store().get(user_id) is None:` to
   `if session.completed:`, ran
   `test_reauth_replaying_session_id_still_does_not_overwrite_edited_mandate`
   → RED (`halal` flipped to `False`, i.e. replay clobbered the edited
   mandate). Restored the original line immediately after
   (`backend/app/api/auth.py` is unmodified in the final diff — confirmed
   via `git diff --stat`).

## Full suite

Run from repo root against the shared venv (worktrees don't have their own
`.venv`; used the main checkout's):

```
cd .claude/worktrees/coder.api-BE-DEF160
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest backend/tests/unit/ -q
```

**Result: 1810 passed, 0 failed, 8 warnings (290.9s).** No failures at all —
including the CR084 test the assign called out as another track's
uncommitted work; it doesn't appear as a failure here because this worktree
is a clean checkout from `main`@6bc6f8ff and never had that other track's
uncommitted `webhooks.py`/test changes in the first place.

**Disclosing a measurement mismatch per the assign's own instruction:**
the assign states baseline **1812**; `--collect-only` in this clean worktree
shows **1806** pre-existing tests (1810 total after my +4). The 1812 figure
was almost certainly measured against the shared main checkout *with* other
tracks' uncommitted changes mixed in (webhooks.py + its test file show as
modified in `git status` there), which a fresh `main`-branched worktree
never sees. Not a regression — just a different, and I'd argue more
correct, baseline for a lane-isolated worktree. Flagging per "if you can
measure that an instruction here is wrong, stop and disclose with the
measurement."

## Mobile half — named precisely

**The backend half is inert without a client change**, same shape as
ROOM-DEF161's finding. Nothing server-side can set `restart=true` on its
own; the Floor footer's "Restart onboarding" control today calls
`POST /v1/onboarding/readback/confirm` with the existing body shape only
(no `restart` field), so shipping just this backend lane changes **nothing
user-visible** — the promise stays false until the client sends the flag.

What the client half needs, as precisely as I can name it without touching
`mobile/`:
- The call site is wherever "Restart onboarding" today calls
  `POST /v1/onboarding/readback/confirm` after the user re-completes the
  interview — almost certainly in the onboarding/concierge feature module
  under `mobile/lib/features/onboarding/` (or equivalent — I did not open
  `mobile/` per the fence, so I can't give the exact file/widget name).
  Find it by grepping the Flutter tree for `readback/confirm` or the
  request model name matching `ReadbackConfirmRequest`.
- That call site needs to (a) know it's in a restart (vs. first-time
  onboarding) — likely already tracked, since DEF158 already changed the
  dialog copy for this exact flow — and (b) thread that through as
  `restart: true` in the JSON body, and (c) send the `Authorization: Bearer`
  header on that call (today's anonymous onboarding flow presumably doesn't
  attach one on this endpoint at all; the restart case must, since the user
  is already signed in).
- The client-side generated/hand-written API client for
  `ReadbackConfirmRequest` needs the new optional `restart` field added to
  its request model to serialize it at all.

**Recommendation**: lane the client half — this backend lane by itself
ships no visible change, and DEF160 should stay `open` (see Registers)
until both halves land together.

## Registers

DEF160 is being left **`open`**, not `fixed` — the user-visible promise
("restart replaces the mandate") is not true end-to-end without the mobile
call site sending `restart: true` + Bearer, which is out of this lane's
fence. Row updated with a DESCRIPTION-column note (status cell stays a bare
token per DEF203); `def_list.md` regenerated;
`docs/defect/_registry/DEF160.row.md` + `docs/defect/def_list.md` committed
together (DEF159).

## Commits

- `cff3d94d` fix(onboarding): restart signal lets an authenticated caller replace their mandate (AT:R65 DEF160)
- `b0ad662a` docs(dispatch): DEF160 register — backend half shipped, left open pending mobile restart signal (AT:R65)
- this hand-off file, committed next.

Branch `lane/BE-DEF160.coder.api`, pushed to origin; merged into `main` in
this same session (fast-forward or merge commit — see `main`'s log for the
exact form).
