# CR / Defect definition of done — AMI Trade bindings

**The questions live in the portable core:**
[`orchestration/DEFINITION_OF_DONE.md`](../../orchestration/DEFINITION_OF_DONE.md).
This file supplies **AMI Trade's answers** to them, plus the rows this project adds.

Read the core first — it defines what a valid disposition is, why the table is **CR-scoped only**
(chunks never render it), and why core rows can be dispositioned but never removed. Filled in when
submitting to the audit handshake; checked by an independent auditor before COMPLETE.

> Restructured by **CR070**. This file used to be the whole checklist, which made it 100% project
> content with no portable half — while both portable loop prompts hardcoded its path, so copying
> the protocol to a new project produced prompts pointing at a file that was not there.

---

## Section A — Verification (is it correct?)

| Row | AMI Trade binding |
|---|---|
| **Scope** | The CR/DEF doc under [`docs/forward_planning/`](../forward_planning/) or [`docs/defect/`](../defect/) — cite its Scope/Acceptance section |
| **Tests** | Backend: `cd backend && .venv/bin/python -m pytest tests/unit/ -q` (~115 s, sqlite tempfile). Mobile: `flutter analyze lib/` + `flutter test`. Quote the observed result, not "green" |
| **Manual verification** | The Mac is a pure editor — there is no local backend. Exercise the real thing: `curl https://api-alpha.agenticmarketintel.ai/v1/…`, `ssh melehost "docker logs ami_api_alpha --tail 50"`, a DB check on melehost, or a release build on a device. `NEEDS-DEVICE-CHECK` is valid when only a physical iPhone can confirm it — Saiful's acceptance test covers it |
| **Scope discipline** | Verified against `git show --name-only <sha>`, not from memory. Never stage `.claude/settings.local.json`, `backend/uv.lock`, `Archive.zip` |
| **Contract integrity** | backend↔mobile is a **hand-mirrored JSON contract, not type-enforced** — a backend rename breaks mobile's `fromJson` at runtime and `?? default` hides it. A cross-domain item re-verifies `fromJson` against **actual backend JSON**, not just that it compiles. `N/A` only when the item touches one side |

## Section B — Deliverables (is it finished?)

| Row | AMI Trade binding |
|---|---|
| **Docs** | `CLAUDE.md` and/or the topic doc under `docs/`; `HANDOVER_*.md` for state the next session needs |
| **Commit tag** | `type(scope): summary (AT:R<N> CR###\|DEF###)` — see [`coding_conventions.md`](../initial_specs/08_tech/coding_conventions.md). Version/build bumps, handover wraps and docs-only commits are governance-exempt and take a plain `(AT:R<N>)` |
| **Register** | [`cr_list.md`](../forward_planning/cr_list.md) or [`def_list.md`](../defect/def_list.md) — quote the row as it now reads |
| **Model / effort / budget** | Tier (`economy\|standard\|premium`, `solo\|ultra`) + the `--max-budget-usd` cap it launched under + one line of justification (CR057). Size on **breadth as well as difficulty** — DEF083 died on `Exceeded USD budget (5)` after editing 31 lessons and before its first commit |

## AMI Trade additions

| Row | Section | The question it asks | Valid disposition |
|---|---|---|---|
| **Config parity** | A | Does any new env-driven setting actually reach the running container? | New settings are forwarded in `docker-compose.yml`'s `api-alpha` block; `backend/tests/unit/test_config_compose_parity.py` enforces it. Twice a shipped feature was dark for months for want of that one line (DEF038, DEF063) |
| **User-facing language** | A | Does anything a user reads misname AMI, or claim a capability the code does not have? | Lesson content, agent prompts, error sentinels and app copy say **AMI** by name, never "the AI" (code, routes and log keys may say LLM). Provenance is **INTERNAL-ONLY** (CR060 §18). No copy may describe a mechanism the code does not implement — that is DEF084, which shipped a false Sharia-screen claim to two app stores |

---

Not a replacement for the register process itself — this table is the **evidence** an independent
auditor checks before calling an item COMPLETE.
