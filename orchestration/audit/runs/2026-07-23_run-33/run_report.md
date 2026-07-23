<!--
Auditor run report — run-33 (2026-07-23, session auditor.core/track U). Round-1 audit of CR050
"tighten login UX + Google Sign-In enablement". Audited SHA 44759a9 (CR050's own commits 28d16e4 +
d1a56a6, both on main/origin). Verdict AWAITING_FIXES. Owner: AUDITOR.
-->

# run-33 (round 1) — CR050 "tighten login UX + Google Sign-In enablement" → AWAITING_FIXES

- **Auditor session:** auditor.core (track U), 2026-07-23. First item picked up from the queue —
  `sh orchestration/audit/watcher.sh state` showed CR050 as the sole `AWAITING_AUDIT` lane, all 34
  others `COMPLETE`.
- **Audited SHA:** `44759a9` (the architect's picked-up-and-verified head; CR050's own commits are
  `28d16e4` "hero OAuth + email disclosure" and `d1a56a6` "Google Sign-In enablement"). Both
  already on `main`/`origin` — `git merge-base --is-ancestor 44759a9 HEAD` confirmed. `git diff
  44759a9..HEAD` over every CR050-touched path is empty except two unrelated later additions (a
  `store_compliance.md` account-deletion row from CR068/CR072, an `app_en.arb` key from DEF084) —
  CR050's own tree is byte-identical at HEAD. Audited in an isolated worktree
  `.claude/worktrees/audit-CR050/` (`git worktree add --detach 44759a9`).
- **The item:** federated Apple(iOS)/Google(Android) sign-in becomes the sign-in-screen hero; the
  email 6-digit-code claim card is demoted behind a "Use email instead" disclosure toggle (hidden
  by default); claim controls are now gated on `!user.isAnonymous` (previously shown to
  already-claimed users too — a real pre-existing bug this CR also fixes); Google Sign-In flipped
  on via a baked default GCP web `client_id` in the two Android build scripts + live
  `GOOGLE_AUDIENCES` on melehost; new Apple Guideline 4.8 coupling note in `store_compliance.md`.
- **depends-on:** none.
- **Verdict:** AWAITING_FIXES (round 1) — zero BLOCKER, **1 MAJOR** (F1, process-completeness: DoD
  table missing 4 rows required by the current `CR_DEFINITION_OF_DONE.md`, restructured by CR070
  ~11h after this lane was submitted), **1 MINOR** (O1, non-blocking wording imprecision), 1
  informational OUT-OF-SCOPE note. No functional defect found anywhere in the CR itself — see the
  reproduction and adversarial sections below.

---

## Suite reproduction (foreground, my own runs, isolated worktree)

Fresh worktree venv lacked the `dev` optional dependency group (`pytest`, `pytest-asyncio`, etc.
not installed by a bare `uv sync`) — same known fresh-worktree fallback seen on other lanes:
`uv sync --extra dev` first.

| Check | Command | Result |
|---|---|---|
| Mobile analyze | `flutter analyze lib/` | **0 errors, 4 pre-existing infos** (`main.dart` deprecated `copyWith` ×2 @ 69:22/69:44, `floor_screen.dart` build-context-across-async-gap ×2 @ 73:7/313:9) — none in CR050-touched files. Matches architect's claim exactly. |
| Widget test | `flutter test test/widgets/sign_in_email_disclosure_test.dart` | **2 passed**: "email claim is hidden behind the disclosure by default", "tapping 'Use email instead' reveals the email claim card". Matches. |
| Named backend suites | `uv run pytest tests/unit/test_config_compose_parity.py tests/unit/test_auth_google.py tests/unit/test_oidc_verifier.py -q` | **26 passed**, 1 pre-existing warning (`room_runner.py:1024` `SyntaxWarning: 'return' in a 'finally' block` — unrelated file, not CR050's). Matches. |
| Full backend suite | `uv run pytest tests/unit/ -q` | **939 passed, 1 warning** (`test_sim_history.py` `HTTP_422_UNPROCESSABLE_ENTITY` deprecation, pre-existing, unrelated). Matches exactly. |

## Source re-read (file:line)

`mobile/lib/screens/auth/sign_in_screen.dart` — compared before/after via `git show 28d16e4`
rather than trusting the after-state alone. **Confirmed a real, in-scope bug fix**: pre-CR050, the
`if (Platform.isIOS) _AppleButton … else if (Platform.isAndroid) _GoogleButton …` block and
`_EmailClaimCard(...)` sat OUTSIDE the `if (user!=null && !isAnonymous) {...} else {...}` branch —
already-claimed users were shown the claim controls too, below their "Signed in as…" card. CR050
moves both inside the anonymous-only `else` branch. `_showEmail` defaults `false` (:55); toggle
`TextButton` only in the `else` arm (:304-314); `_EmailClaimCard` only when `_showEmail` (:294-303)
— exactly what the widget test asserts.

## Blind adversarial pass — riskiest dimension

The CR's one genuinely untested claim end-to-end (no Android device this session, disclosed) is
whether Google Sign-In is *actually* wired correctly, not just declared wired. The failure mode if
it isn't: every real Google sign-in silently fails the backend's `aud` check, and nothing in the
test suite would catch a client_id/audience mismatch because both sides are configured
independently. Reproduced live, not trusted from the architect's prose:

```
$ ssh melehost "docker exec ami_api_alpha printenv | grep -i GOOGLE"
GOOGLE_AUDIENCES=153141744056-03d6sabmvita0a2civs6e0ngjoac54v7.apps.googleusercontent.com
```

- `scripts/install_android.sh:37` / `scripts/build_playstore.sh:52` bake the **identical**
  client_id as the shell default.
- Both scripts pass it through for real: `--dart-define=GOOGLE_OAUTH_WEB_CLIENT_ID="${GOOGLE_OAUTH_WEB_CLIENT_ID}"`
  (`install_android.sh:90`, `build_playstore.sh:113`) — not a shell default that dead-ends before
  reaching the compiled binary. `sign_in_screen.dart:37-38`'s
  `String.fromEnvironment('GOOGLE_OAUTH_WEB_CLIENT_ID', defaultValue: '')` will pick it up.
- `docker-compose.yml:108`: `GOOGLE_AUDIENCES: ${GOOGLE_AUDIENCES:-}` forwarded into `api-alpha`
  (CR040 degrade-loudly / compose-parity satisfied; `test_config_compose_parity.py` passed above).
- **No mismatch.** The single highest-value untested claim in this CR holds up.

Second adversarial check — the new Apple Guideline 4.8 compliance claim in `store_compliance.md`
("iOS shows only Apple, so 4.8 is satisfied") is verified structurally in code, not accepted as
documentation: `if (Platform.isIOS) ... else if (Platform.isAndroid) ...` is mutually exclusive by
construction, so Google literally cannot render on iOS in this file. Holds.

## Scope discipline

`git show --stat 28d16e4` → 11 files (screen, `app_en.arb` + 3 generated l10n outputs, widget test,
`store_compliance.md`, 2 new CR050 doc files, `cr_list.md`). `git show --stat d1a56a6` → 3 files
(`google_signin_enablement.md`, `build_playstore.sh`, `install_android.sh`). All CR050-scoped, no
drive-by changes. `cr_list.md` CR050 row reads `in_progress` — accurate (Android on-device claim
still genuinely open, not overclaimed as `done`).

## Contract integrity

`git diff` over both CR050 commits touches neither `backend/app/api/auth.py` nor
`backend/app/services/auth_service.py` — the `signInWithApple`/`signInWithGoogle` response shapes
consumed by `auth_providers.dart` are untouched. N/A holds, confirmed not assumed.

## Findings

**F1 — MAJOR (process-completeness, not a functional defect).** `CR050.architect.md`'s DoD table
carries the pre-CR070 row set (Scope, Tests, Manual verification, Docs, Commit tag, Register, Scope
discipline). `CR_DEFINITION_OF_DONE.md` — restructured by CR070 (`89dbe8c`, **2026-07-23 03:17**,
~11h **after** this lane's `SUBMITTED: round 1` at **2026-07-22 16:01**) — now also requires
**Contract integrity**, **Model / effort / budget**, and the AMI Trade additions **Config parity**
and **User-facing language**. None of the four appear. `DEFINITION_OF_DONE.md` is explicit that
core rows may be dispositioned but never omitted, and I audit against the template in force today,
so this bounces despite being a timing artifact rather than sloppy work. To keep the round-2 fix
near-zero-effort I independently verified 3 of the 4 myself this round (see `CR050.auditor.md` for
the exact dispositions to paste in): Contract integrity (N/A, confirmed above), Config parity
(confirmed above, live + forwarded), User-facing language (only new string is "Use email instead",
no AI-naming/capability-overclaim issue). Model/effort/budget is the architect's own to answer —
the lane file says these commits were "authored directly," not a dispatched `coder.*` task, which
may mean a reasoned `N/A` or may need a real tier/cap; I can't determine that from outside.

**O1 — MINOR, non-blocking.** DoD's "Manual verification" row overstates coverage: "iOS path
(Apple hero + email disclosure) is verified via the widget test" — but the widget test's own
docstring discloses `Platform.isIOS`/`isAndroid` are both `false` on the macOS test host, so it
never exercises the Apple button, only the platform-independent email-disclosure toggle. No
functional risk: `_AppleButton`'s render logic is pre-existing, unmoved-in-logic code (only its
*position* changed, now gated on `isAnonymous`, confirmed above) — not new CR050 logic escaping
test coverage. A wording fix, not a code or test fix.

**OUT-OF-SCOPE (informational).** `room_runner.py:1024: SyntaxWarning: 'return' in a 'finally'
block`, surfaced during the full-suite collection. Pre-existing, unrelated file, doesn't fail
anything. Not minting a DEF — trivial/stylistic; architect's call whether it's worth one.

## Verdict

Zero BLOCKER. One MAJOR (F1) — bounce for DoD-table completeness only. Every substantive
Section-A claim (Scope, Tests, both adversarial probes, Scope discipline, Contract integrity,
Config parity) independently re-verified correct with zero functional defects found.

**VERDICT: AWAITING_FIXES (round 1)**
