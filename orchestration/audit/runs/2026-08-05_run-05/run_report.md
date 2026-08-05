# Audit run 2026-08-05 run-05 — CR136-M08, round 1

Audited at **`c0f1ac86`**, not the declared `c56e2c41`. M07's blocker fix
`d3e4f5a60029` is absent at the declared SHA and changes the exact object this
lane's dedupe rides on: a plain `UniqueConstraint` became a **partial** unique
index (`deleted_at IS NULL`), and `find_by_dedupe_key` gained a tombstone filter.

Verdict: **COMPLETE (round 1)** — zero BLOCKER, zero MAJOR, 2 non-gating MINOR.

**MINOR m1** — §5.1, the lane's headline self-reported defect, no longer exists.
Its probe re-run verbatim against the real store:

```text
                                  §5.1 claims          measured at c0f1ac86
3. route's idempotency read       the tombstone        None
4. re-write, same dedupe_key      created=False, same  created=True, NEW id
5. client opens the id            store.get -> None    a live entry
6. gate counters                  used=1 daily_used=1  used=2 daily_used=2
```

Every line inverts. §5.5 is stale the same way (`46bf51ae` made both counters
per-user). A provenance defect, not a behaviour one — the code is right.

**MINOR m2** — `reference_id` still unindexed (`models.py:300`), self-disclosed.

Probed beyond the submission, since the old analysis could not ask it: 5×
(create, delete) on one key yields 5 rows and `used=5 daily_used=5` — replay
*costs* budget rather than resetting it, the safe direction — and restoring a
tombstone whose key a live row holds returns `RestoreOutcome.SUPERSEDED` with the
live row staying authoritative.

Reproduced: backend module **20 passed**, `flutter test` **+10**, `flutter
analyze` **6 issues / 0 errors** (same six files), QA-A…D **1/1/1/1** with
matching names, full `tests/unit/` **2318 passed**. QA-A still kills after the
partial-index rewrite, so the "enforced in the database" property survived a
change made by another lane.
