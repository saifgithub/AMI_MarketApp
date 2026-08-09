# CR158 — Stamp a prompt version, so a measurement can tell which prompt produced it

**Filed:** 2026-08-08 · **Status:** proposed · **Trigger:** Saiful, 2026-08-08 —
*"when will we update the frontmatter?"*, asked after DEF241/DEF243 changed prompt
bytes in three `content/agents/*.md` files.

## The direct answer first

Nothing needed updating. The frontmatter is four identity keys —
`agent_id`, `display_name`, `family`, `role_color` — identical in shape across all
13 agent files, carrying no version, no date, and no checksum. **Nothing in the
backend parses it.**

## Why the question is the right one anyway

There is no prompt version anywhere in the system.

| where you'd look | what's there |
|---|---|
| `content/agents/*.md` frontmatter | 4 identity keys, no version |
| `llm_audit` (19 columns) | `system_prompt` verbatim; nothing saying which generation |
| `room_runs` | no prompt field at all |

So the only way to know which prompt produced a stored turn is to take its
timestamp and reconstruct it against `git log`. By hand. With nothing checking it.

### That cost is already paid, twice

**A published figure was wrong.** CR143 filed an 18.4% PM-reformatter rate,
measured over a 30-day pool that straddled a prompt change. On the current epoch
it is **0/18** — 2026-07-30 alone contributed 15 of the 22 reformats and every
day from 07-31 on was zero. The same pooling made stance emission read 4.5%
because 1,682 of the pooled turns predated the envelope shipping at all. Both were
caught late and corrected in the register.

**Four subagents each rediscovered the same trap.** `real_samples/*.prompt.txt`
for the market, news, research-manager and trader agents are pre-DEF228 captures
rendering a fact-sheet shape HEAD can no longer emit. Each of the four processing
agents had to work that out independently, from the bytes, because nothing in the
file says which generation it is. Two of the eighteen corpus convenes straddle a
mid-epoch promotion, and nothing in the data says so either.

The epoch boundaries this programme runs on are four commit SHAs — `7fc09420`
(CR105), `258625a7` (DEF227-229), `06098b4f` (DEF233/231/232), `3f4d33d2`
(DEF234) — carried in a README and in my head. That is a shared mutable fact with
no writer and no check, which is the shape CR052 forbids everywhere else.

### And it matters this week

**DEF241 and DEF243 both owe a post-promotion re-measure.** Their acceptance is
"the rate moved", which requires separating pre- from post-promotion turns. Today
that separation is timestamp-versus-deploy-time, done by hand — the exact step
that already produced one wrong number here.

## Scope

> **DEVIATION FROM THIS SCOPE, recorded rather than quietly taken (2026-08-09).**
> Item 1 below says the version goes *in each agent file's frontmatter*, and it
> does not. The two halves of that sentence contradict each other: a value that is
> "derived, never hand-maintained" cannot also live in a hand-edited content file
> unless something writes it there — and a generation step that rewrites
> `content/agents/*.md` is a **new drift surface**, the precise failure this CR
> exists to prevent. Someone edits a prompt, forgets to regenerate, and the
> frontmatter now asserts a version that is false. Worse than none, by this CR's
> own argument.
>
> So the version is computed from the assembly and never stored in the content.
> The frontmatter keeps its four identity keys. Everything else in item 1 —
> derived, covering all layers, impossible to forget in a commit — is delivered,
> and is delivered *more* strongly by not writing it down.

### 1. `prompt_version` — derived from the assembly, never hand-maintained, never stored in content

A short content hash, computed at import over the **six assembly layers**, not
over the base file alone: `GROUNDING_DIRECTIVE`, the base `.md`, the mandate
overlay, the user overlay, the format constants (`_LENGTH_GUIDE`, `_PROSE_FORMAT`,
`_STANCE_FORMAT`, `_PM_VERDICT_FORMAT`), and the safety floor.

The base file is **10–18% of what the model receives** (2,332 of 12,759 chars for
the PM pre-transcript). A version derived from the file alone would have been
unchanged by DEF236's format fix or DEF241's snapshot change — it would say
"same prompt" about a materially different prompt, which is worse than no version.

Hand-written semantic versions are explicitly rejected: they drift silently, and a
drifted version is worse than none. `INDEX.md` in the audit lane went stale
exactly this way and the file now carries a warning saying so.

### 2. One nullable column on `llm_audit`

`prompt_version`, written by the gateway alongside `system_prompt`. Additive and
nullable — old rows stay NULL, which honestly reads as *unversioned*, not as
*version zero* (CR040 degrade-loudly; the same distinction `cache_write_tokens`
already draws in that table's own docstring).

Migration shape is CR141's (`2a08e21c0dac`) — the last column added to this table.
DEF215's rule applies: Alembic owns the table, `init_schema` must not `create_all`
it.

### 3. A guard so a new agent cannot ship unstamped

The same shape as `test_def141_audit_pins_are_collected.py`: iterate
`content/agents/*.md`, assert every one resolves a version, and assert the
assembled-layer set the hash covers is the set the builder actually uses — so
adding a seventh layer without adding it to the hash fails the build rather than
silently narrowing what "version" means.

## Out of scope

- **Backfilling historical rows.** The SHA reconstruction in
  `CR143_agent_prompt_audit/README.md` stays the record for pre-CR158 epochs.
- **Any change to what the prompts say.** This CR adds a stamp, nothing else.
- Versioning the 1-on-1 / Concierge / Brief surfaces beyond what falls out of the
  shared assembly path — they have 8/13/6 rows in 30 days and no corpus to
  partition.

## Acceptance

- Two convenes either side of a deliberate prompt edit carry **different**
  `prompt_version` values; a convene with no prompt change carries the same one.
- Changing a format constant (not a base file) changes the version — the case a
  file-only hash would miss.
- A new agent file with no version fails the guard.
- `pytest backend/tests/unit/ -q` green; `test_config_compose_parity.py` green
  (no new env, but the migration is real).

## Sequencing

Build it **before** the DEF241/DEF243 promotion if it can be done that fast —
that promotion's acceptance is the first thing it would make exact, and there are
three more prompt-byte changes queued behind it (DEF240, CR145 Tier A/B, DEF236).
Otherwise ship immediately after and accept one more hand-partitioned measurement.

Not a blocker for the fixes themselves; it is a blocker for *trusting the next
measurement of them*.
