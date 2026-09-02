# 02 — Design: the generated "data boundary" block

The core recommendation. The root cause CR219 names — "an agent's prompt is two halves
nothing binds together" — is not fixed by correcting the eight false denials, because
the next CR that adds a sheet field recreates the bug (CR179 did it in an afternoon;
CR164, CR160 and CR218 each walked past it). The fix is to make hand-written
availability claims impossible: **generate the availability statement from the same
code that renders the sheet**, so a prompt that lies about the sheet cannot be built.

## 1. Module layout

| File | Change |
|---|---|
| `backend/app/services/sheet_registry.py` | **NEW.** Single source of truth: `SHEET_LINES`, `SHEET_ABSENTS`, `render_data_boundary_block()`. Imports only `app.schemas.AgentId` — pure data + renderer, importable by both `room_prompts` and `agent_prompts` without cycles. |
| `backend/app/services/agent_prompts.py` | Inject the block in `build_agent_prompt` (L49) between persona base and mandate overlay; new `surface` kwarg; `clear_prompt_cache()` also clears the block cache. |
| `backend/app/services/room_prompts.py` | One line: `build_room_messages` passes `surface="room"` through. `_AGENT_LANES` (L1771) stays put; the registry duplicates the domain column and the sync test proves the two agree. |
| `backend/app/agents/overlay_generator.py` | `_fundamentals_block` / `_market_analyst_block` reworded to demand only registry-backed lines (Class C #15/#16, Class B #9). |
| `content/agents/*.md` | Strip availability claims; keep voice and method. |
| `backend/tests/unit/test_cr219_sheet_registry_sync.py` | **NEW** — registry ↔ renderer bidirectional sync. |
| `backend/tests/unit/test_cr219_availability_claims_guard.py` | **NEW** — whole-file denial scan, truth resolution, byte-identity, overlay-demand backing. |
| `backend/tests/unit/test_cr105_analyst_inputs_field_state_guard.py` | Amended in lockstep with persona edits; its presence-only `_NEGATIVE_CLAIMS` checks retire, superseded by the truth-checked guard. |

## 2. Registry shape

```python
class SheetLine(NamedTuple):
    line_id: str                      # "margin_trend", "buybacks", "pe", ...
    domains: frozenset[str]           # ⊆ {"fundamentals","technicals","news","social"};
                                      # frozenset() = CORE (identity, reference price)
    label: str                        # "Margin trend, YoY"
    marker: str                       # literal substring present in EVERY rendered
                                      # variant of the line — the sync probe
    field_state_keys: tuple[str, ...] # every field_state key the render site gates on
    supports: str                     # "YoY direction of gross/operating/net margin, in bps"
    limit: str | None                 # "direction over the trailing-year comparison;
                                      # NOT a monthly/quarterly series"
    surfaces: frozenset[str]          # {"room", "one_on_one"}

class AbsentItem(NamedTuple):
    absent_id: str                    # "peer_basket_pe", "historical_median_multiples", ...
    domains: frozenset[str]
    label: str
    note: str                         # one clause on why it's absent
    collision_markers: tuple[str, ...] # substrings that, if they EVER appear in the
                                       # fully-populated rendered sheet, prove this
                                       # denial false → guard goes red
```

Granularity is the **rendered line** (the render unit and the persona-claim unit), not
the field — `_margin_structure_line` reads three keys but is one claim surface.
`collision_markers` is the forward-in-time guarantee and the exact inversion of today's
bug: when a future CR ships interest coverage, the `interest_coverage` absent entry's
marker appears in the rendered sheet and the build fails until the entry is deleted.
Drift now breaks red in both directions — a new line without a registry entry, and a
registry absence contradicted by a new line.

Key signatures:

```python
def lines_for(agent_id, surface="room") -> tuple[SheetLine, ...]
def absents_for(agent_id) -> tuple[AbsentItem, ...]
@lru_cache(maxsize=64)
def render_data_boundary_block(agent_id, surface="room") -> str
```

## 3. Schema-level, injected in `build_agent_prompt`

The block states **schema-level** availability — "the sheet MAY carry each item below;
a field renders tagged (LIVE) when real and 'not available' otherwise" — not per-ticker
runtime state. Rationale:

- **Runtime truth already has an owner**: the sheet's own `(LIVE)` tags,
  "not available" lines, and `_historical_mode_line`. A second runtime rendering in the
  persona layer is two in-prompt statements of one fact that can disagree. The block's
  footer keeps the deference: *"the sheet's own statement for this run always wins."*
- **`build_agent_prompt` has no profile and should not grow one** — threading the Room's
  per-run profile into layer 3 drags run data into the 1-on-1 and Brief-Your-Agent
  composition paths for no gain.
- **One injection point fixes both surfaces.** The block is a function of
  `(agent_id, surface)` only, so Room and 1-on-1 (Class E) get it from the same call —
  which is what closes the "every denial is doubled" problem. Injecting in the CONVENE
  block instead would leave the 1-on-1 surface unfixed.
- **Prefix-cache friendly**: static-per-agent content early in the prompt; the CONVENE
  block stays the per-turn tail.

Placement: `base + "\n\n" + data_boundary + "\n\n" + overlay` — under the persona so it
reads as the authoritative replacement for the `## Inputs` availability bullets, above
the mandate overlay so the overlay's demands are read against it. Header sketch:

```
─── DATA BOUNDARY (generated from the renderer — this section cannot drift) ───
The fact sheet MAY carry each item below; every field renders tagged (LIVE) when
real and "not available" otherwise. The sheet's own statement for this run always
wins. Nothing on the DO-NOT-HAVE list is withheld from you deliberately — it is
not fetched for any ticker; say "not supplied" rather than estimating it.
```

The "not withheld deliberately" sentence directly counters the misread the record
caught: an agent classified a real data need as WITHHELD on the strength of a false
denial and stopped asking.

Per-agent shape: the **4 analysts** get line-level, lane-filtered blocks (replacing
their `## Inputs` availability bullets ≈ token-neutral). The **8 downstream agents**
get a compact grouped digest — four domain paragraphs built from `label`s plus the
absent list, ~⅓ the token cost — which *is* the Class-D acknowledgment Saiful chose.

## 4. Sync test (`test_cr219_sheet_registry_sync.py`)

Render a fully-populated fixture profile (factor the sentinel fixtures out of
`test_prompt_data_parity.py` into a shared `backend/tests/unit/sheet_fixtures.py` —
`evidence/dump_sheets.py` already proved the reuse works) through
`_format_profile`, then:

1. Every rendered body line maps to exactly one registry `marker` — an orphan line
   fails, naming it. **This is the drift-proof: the next sheet-adding CR goes red until
   a registry entry (with its supports/limit note) is authored.**
2. Every registry entry renders — a dead marker fails.
3. Per-analyst: rendered `line_id` set equals the registry's lane filter — proves
   `domains` ≡ `_AGENT_LANES` without an import dependency.
4. Union of `field_state_keys` equals the key universe imported from `room_runner`
   (same import trick as `test_cr105`'s `_FIELD_STATE_KEY_UNIVERSE`, so a rename breaks
   a test, not silently nothing).
5. `build_live_data_block` (fetch monkeypatched to the sentinel) maps bidirectionally
   to entries with `"one_on_one"` in `surfaces` — Class E documented structurally.
6. Red/green demos in the file, test_cr105's own pattern: the matcher demonstrated red
   against a planted fake rendered line and against the registry minus `margin_trend`.

## 5. Claims guard (`test_cr219_availability_claims_guard.py`)

**(a) Whole-file scan** — every `content/agents/*.md`, all sections (not the
`## Inputs`→`## Output` window that let findings 2/6/7/8 escape), against a denial
pattern set (`not (available|supplied|provided|…)`, `(do not|never) (have|receive|…)`,
`no … (history|series|baseline)`, `never (describe|cite|quote)`, `cannot (say|support)`,
`you have no`, `unavailable`, …). Every hit must resolve in an allowlist as one of:
a true `absent_id`, `RUNTIME_DEFERENCE` (the "sheet wins" boilerplate), or
`ROLE_BOUNDARY` ("that's the Technical Strategist's job" — a lane statement, not an
availability claim).

**(b) Truth resolution** — each allowlisted `absent_id` must exist in `SHEET_ABSENTS`
AND none of its `collision_markers` may appear in the fully-populated rendered sheet
AND no allowlisted phrase may contain any `SheetLine.marker`. This is the TRUTH check
`test_cr105` never had — "never describe a margin as rising" fails today against
`Margin trend`'s marker.

**(c) Byte-identity** — for all 12 agents × both surfaces,
`render_data_boundary_block(a, s)` occurs exactly once, verbatim, in
`build_agent_prompt(...)` output (unit-buildable Mandate, no store, no sqlite).
Composition can never paraphrase or truncate the registry.

**(d) Red fixtures** (CR219 acceptance #1 and #2, verbatim):
- a false denial planted in a `## Voice` section fails, quoting file/line/pattern —
  proves the window blind spot is closed;
- a fabricated `AbsentItem` with `collision_markers=("Margin trend",)` fails against
  today's sheet — proves the truth check fires.

**(e) Overlay arbitration** — `test_overlay_demands_are_registry_backed`: an authored
map from overlay demand phrases (across the horizon/path branches of
`_fundamentals_block`/`_market_analyst_block`) to `line_id`s; a demand resolving to no
registry line fails. Class C #15 goes red at authoring time under this test, which is
what CR146's hand-sweep could not guarantee.

All pure-unit: registry + `_format_profile` + fixture dicts; monkeypatch only for the
1-on-1 fetch seam. Stale-allowlist entries fail too (test_cr105's anti-rot rule, kept).

## 6. Sizing

Analysts ≈ neutral (the block replaces their `## Inputs` bullets; the Fundamentals
Analyst's ~700-token list is the largest). Downstream 8 ≈ +150–250 tokens each →
roughly **+1.5–2.5k prompt tokens per convene** across 12 prompts — small against the
5.7k-char sheet ×8 and the growing transcript, which dominate. No `_AGENT_MAX_TOKENS`
interaction (that is the decode budget; the block asks for no extra output). Do
re-check the longest prompt (PM at VERDICT with ladder + transcript) against the served
context length, and regenerate `evidence/` snapshots (`assemble_room.py` output
changes).

## 7. Migration order

1. Land `sheet_registry.py` + sync test alone — registry proven before anything
   depends on it.
2. Inject the block for all 12 (+ byte-identity test). Prompts grow; nothing
   contradicts yet. Regenerate evidence snapshots.
3. Persona edits, **one agent per commit, analysts first** (fundamentals → market →
   news → social): delete the 8 false denials and the superseded availability bullets;
   keep method prose reworded availability-free (keep the gross-vs-net "cost problem vs
   pricing problem" teaching; drop "what you do not have is a margin trend"). Delete
   the 3 true denials from prose too — they live in `SHEET_ABSENTS`; **a growing
   allowlist is the old failure mode returning.** Each commit updates `test_cr105`'s
   mappings in lockstep (atomicity: persona edit + mapping edit land together or CI is
   red mid-migration).
4. Claims guard fully green by the last slice of step 3.
5. Downstream-8 `## Inputs` acknowledgment in **its own commit** — Class D changes what
   8 agents argue from; the banked 66-turn corpus is the before-arm.
6. Overlay generator consults the registry: the short/medium fundamentals branch
   (overlay_generator.py:447) rewritten to registry-backed momentum ("YoY margin
   trend, TTM revenue growth, the next consensus-EPS date"), dropping
   revisions/surprise-history/guidance; market-analyst trend demands phrased in the
   registry `limit` vocabulary ("direction over the 64-day window, not a
   month-over-month series").
7. Follow-ups: concierge + Brief-Your-Agent sweep (26 of 38 prompts unswept); the free
   fields land through the registry and exercise the `collision_markers` red path for
   real (see `03`).

Instruction-fight collisions (#10–#14) are explicitly **outside this mechanism** —
they are not availability claims; per-finding resolutions in `03`.

## 8. Risks

- **Denial-regex false positives** in voice prose ("no 'to the moon' language") →
  allowlist churn. Acceptable: every hit forces a human resolution, which is the
  mechanism working; `ROLE_BOUNDARY`/`RUNTIME_DEFERENCE` absorb the recurring benign
  shapes.
- **Marker brittleness** — rewording a sheet line breaks the sync test. Intended (red
  on drift is the feature); keep markers to the shortest stable noun ("Buybacks", not
  the sentence).
- **Double-truth within one prompt** vs `_historical_mode_line`/withheld tiers —
  mitigated by the "sheet wins" footer being part of the generated block, not persona
  prose.
- **Cache staleness** — `render_data_boundary_block` is lru-cached;
  `clear_prompt_cache()` must clear it or a hot process serves a stale block after a
  registry edit.
- **CR038 humility** — the block is still prose to the model (~30% instruction
  compliance). The guarantee this design delivers is that **the prompt never lies**,
  not that the model always obeys. The measurable claim is citation-rate movement
  (24% → toward the 95% undenied neighbourhood), per the trailing AC4.
