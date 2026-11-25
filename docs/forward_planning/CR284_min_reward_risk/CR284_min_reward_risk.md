# CR284 — Minimum reward to risk as a mandate setting

Filed 2026-11-25 (AT:B1). Owner: track B.

## Why

The coded decision rule (CR267 WP-23) and the deterministic mandate check never compare a Room's target with its stop. In the Bursa 200 batch (CR282 §11), 2 of 24 approvals risked more than they targeted (5285.KL SD Guthrie: entry RM6.00, stop 5.64, target 6.155, reward:risk 0.43; 4006.KL Oriental 0.80) and 9 of 24 were below 1.5:1. Narrowing the terminal veto (CR267, terminal v2) will let more buys through, so the gap widens.

Saiful 2026-11-25: asked whether this belongs in the user's risk appetite; chose **"Mandate field, default by risk"**.

## What

1. New mandate field `min_reward_risk` (number, ratio of target distance to stop distance from entry).
2. Default from the risk score when the mandate is created or the risk score changes and the user has not set it: risk 1–2 → 2.0, risk 3–4 → 1.5, risk 5 → 1.0.
3. Editable in Settings (mandate section), with an explain sheet; shown in the onboarding readback.
4. Enforced by the deterministic mandate compliance check (the uncoachable floor), not by prompt: a Room verdict of APPROVE whose (target − entry) / (entry − stop) is below the floor becomes REJECT with a violation that names both numbers, the same path as the single-name cap. A verdict with no entry, stop or target is untouched (PASS/HOLD carry none).
5. Applies to US and Bursa Rooms alike. Short-side geometry (if ever enabled) uses the mirrored distances.
6. Existing mandates without the field get the risk-score default at read time and say so (no silent zero).
7. Strings seeded for AR/MS with context comments (translation is external).

## Out of scope

Manual sim orders (a user's own ticket) — no target is required there.

## Acceptance

1. Unit tests: default per risk level; user override honoured; APPROVE below the floor → REJECT with the violation text; exactly at the floor passes; missing levels untouched; Bursa and US.
2. The Room bank/cache key includes the floor so a changed floor never serves a stale verdict.
3. UAT cases updated (mandate + room areas); device check on the next build.
4. Re-scoring the Bursa batch's 24 approvals at the risk-5 default (1.0) rejects exactly SD Guthrie and Oriental.
