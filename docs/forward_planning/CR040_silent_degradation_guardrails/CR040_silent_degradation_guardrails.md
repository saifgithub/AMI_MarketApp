# CR040 — Guardrails against silent degradation (executable config parity + pattern register)

**Status:** done (all three layers landed; DEF063 compose fix included, keys parked pending budget call) · **Filed:** 2026-07-17 (AT:R59) · **Requested by:** Saiful ("I want to ensure
we never make the same mistake twice. how do we document this problem?")
· **Prevents recurrence of:** [DEF038](../../defect/) (OIDC audiences unforwarded),
[DEF063](../../defect/DEF063_adanos_alpha_vantage_keys_never_forwarded/) (Adanos + Alpha Vantage
unforwarded) · **Names but does not fix:** DEF058, DEF059, CR037, CR038

## Why — the documentation we already had is what failed

The DEF038 lesson was written as a comment at `docker-compose.yml:103`:

> `# OIDC audiences (DEF038: these lived in .env but were never forwarded here, so the container`
> `# verified Google tokens against an empty audience list).`

`ADANOS_API_KEY` should have been added ~7 lines below it. It wasn't, and the feature was dark
for the entire life of CR024 until a benchmark tripped over it. Two failure modes, both
structural rather than personal:

1. **Descriptive, not imperative.** It explained a past bug about two specific keys; it never
   stated a rule binding on every future key.
2. **Nothing executed it.** A comment only fires if a human opens that file at that moment.
   CR024's work lived in `config.py` + `social_context.py` — compose was never opened.

Conclusion: **writing DEF063's lesson into more prose repeats the DEF038 experiment.** The
documentation must run.

## The wider pattern this belongs to

AT:R59 surfaced four instances of one meta-pattern — **every degradation path in AMI is silent
and confident**:

| Instance | Trigger | Degraded behaviour | Signal to anyone |
|---|---|---|---|
| DEF063 | API key not forwarded | synthetic sentiment scaffolding | none |
| DEF059 | vLLM host down | confident scripted **APPROVE** verdict | none (looked like a fast run) |
| DEF058 | PM verdict unparseable | silent PASS (22% of runs) | log line only |
| CR037 / CR038 | no social / no macro feed | invented facts asserted unhedged (23/32, 62/88) | none |

The invariant that should hold instead: **degrade loudly, never confidently.**

## Scope

**Layer 1 — executable guard (the prevention).**

1. `backend/tests/unit/test_config_compose_parity.py` — assert every *feature-gate* field in
   `Settings` (`backend/app/core/config.py`) appears in `docker-compose.yml`'s `api-alpha`
   environment block. Fails at commit time, on the Mac, inside the existing suite. Needs an
   explicit allow-list for fields that legitimately never reach the container (e.g. renamed
   forwards: `AMI_ENV`→`ENV`; tunnel-only: `CF_TUNNEL_TOKEN`→`TUNNEL_TOKEN`) so the test states
   intent rather than pattern-matching.
2. `GET /v1/admin/config-check` (`backend/app/api/admin.py`, behind the existing `get_admin`
   dependency) — report each feature gate's in-container on/off state. Never echo secret values,
   only booleans. Turns "is Adanos live?" from archaeology into one curl.
3. `/promote-to-alpha` step — after the health poll, call config-check and fail the promotion
   loudly on any key populated in `infra/alpha.env` but dark in the container.

**Layer 2 — `docs/initial_specs/08_tech/failure_patterns.md`** (new; no cross-cutting doc exists
today — only per-instance registers, which is exactly why DEF038's lesson never generalized).
One entry per failure **class**: symptom, instances, why the previous guard failed, and the
executable check that now enforces it. **House rule: an entry without an enforcing check is not
done.** Seed with two entries: *unforwarded config* (enforced by Layer 1) and *silent confident
degradation* (principle recorded; per-instance fixes tracked in DEF058/059, CR037, CR038).

**Layer 3 — one line in `CLAUDE.md`** under the behaviour-critical rules — the only doc
guaranteed to load every session:

> Degrade loudly — any feature gated on config presence must fail visibly, never silently fall
> back. New env-gated setting ⇒ compose env block + parity test. See
> `docs/initial_specs/08_tech/failure_patterns.md`.

## Out of scope

Executable guards for the other three instances (outage / parse-failure / unhedged-fact
degradation). DEF058 and DEF059 are already fixed and regression-tested; CR037 and CR038 are
undecided. This CR only records the principle they share.

## Acceptance

1. `test_config_compose_parity` fails when `ADANOS_API_KEY` is removed from the compose block —
   i.e. it would have caught DEF063 and DEF038 (verify by reverting the fix locally).
2. `GET /v1/admin/config-check` reports `adanos`/`alpha_vantage` gate states truthfully on Alpha,
   leaks no secret values, and 403s without `ADMIN_SECRET`.
3. `/promote-to-alpha` aborts on a deliberately unforwarded populated key.
4. `failure_patterns.md` exists with both seed entries; every entry names its enforcing check.
5. `CLAUDE.md` carries the one-line invariant.

## Risks

- Parity-test allow-list becomes a dumping ground — each entry must carry a one-line reason.
- config-check must never echo secret values; assert booleans only (test for it).
- DEF063's compose fix itself is **not** in this CR (it's a metered-API decision — Adanos free
  tier is 250 calls/month). This CR ships the guard; DEF063 ships the key.
