# CR136 build — M08: Journal integration

> Conforms to CR136 Rev 4 + build/README.md. Where this doc and Rev 4 disagree, Rev 4 wins.

## 1. Purpose

Make a Portfolio Health Finding a first-class Decision Journal citizen, on both
sides of the wire. Implements Rev 4's **"Journal storage plan"** section: the
`EntryType.PORTFOLIO_HEALTH_ANALYSIS` enum member (backend + Dart, in one
commit — the DEF210 parity test binds them), the pinned journal-entry shape
(README interface contract 5), the two journal reads M07's gating/idempotency
needs, and the mobile rendering path: card accent + label, and a detail-screen
branch that renders the **stored** head-disclosure block + §F1–§F5 markdown —
never a regeneration (SCREEN_DESIGNS §17+: *"an archived report always reads
as it did when filed"*). Depends on M06 only for the artefact shape (README
contract 5); buildable and testable before M06/M07 exist.

## 2. Files

**Anchor corrections vs Rev 4's prose, verified at HEAD:** the journal DB
model is `backend/app/db/models.py:267` (not `backend/app/models.py`); the
journal screens live under `mobile/lib/screens/journal/` (not
`mobile/lib/screens/`); the `_accent`/`_label` switches sit at
`journal_screen.dart:430-453` / `:455-478`.

New files (each opens with the stated header docstring one-liner):

| File | Header one-liner |
|---|---|
| `backend/app/services/portfolio_health_journal.py` | `"""CR136 M08 — maps a rendered Portfolio Health Finding (M06 artefact) to its Decision Journal entry (pure mapper, no DB access)."""` |
| `backend/tests/unit/test_portfolio_health_journal.py` | `"""CR136 M08 — journal integration: enum member, Finding-entry shape, store reads for gating/hysteresis."""` |
| `mobile/lib/widgets/journal/finding_sections.dart` | `/// CR136 — renders a STORED Portfolio Health Finding (head disclosure + §F1–§F5 markdown) verbatim; shared by the Journal detail branch (M08) and the Finding detail screen (M09). Never recomputes.` |
| `mobile/test/models/journal_entry_type_test.dart` | `// CR136 M08 — wire mapping for portfolio_health_analysis + the DEF210 null-on-unknown contract.` |
| `mobile/test/widgets/finding_sections_test.dart` | `// CR136 M08 — stored Finding renders disclosure FIRST, then §F1–§F5, from payload only.` |

Touched files (anchors verified at HEAD 645de77c):

- `backend/app/schemas/journal.py:25-34` — `EntryType`, currently 9 members.
- `backend/app/services/journal_store.py` — two new `JournalStore` methods
  (class starts :77; `append` coercion at :84-86 is the reason the enum member
  must exist; module-level `_row_to_entry` reused by the new reads).
- `backend/tests/unit/test_journal_entry_type_parity.py` — **no code change**;
  see §3.3 for exactly why and what it forces instead.
- `mobile/lib/models/journal.dart` — enum `:4-14`, `wire` `:17-38`, `fromWire`
  `:40-62`, nullable `entryType` design `:86-91` (**preserve** — see §3.5).
- `mobile/lib/screens/journal/journal_screen.dart` — `_accent` `:430-453`,
  `_label` `:455-478` (both exhaustive incl. `case null`; the compiler forces
  the new cases).
- `mobile/lib/screens/journal/journal_detail_screen.dart` — `_PayloadBlock`
  branch chain `:255-347`; generic bare-`Text` fallback `:342-346` (renders via
  `_Block`, whose body is `Text(...)` at `:550`).
- `mobile/lib/l10n/app_en.arb`, `app_ar.arb`, `app_ms.arb` — one new key each
  (`mobile/test/l10n_key_parity_test.dart` fails on any missing locale).

## 3. Implementation spec

### 3.1 Backend enum member

Append to `EntryType` (`backend/app/schemas/journal.py:34`, after
`DAILY_CHALLENGE`):

```python
    PORTFOLIO_HEALTH_ANALYSIS = "portfolio_health_analysis"
```

**No DB migration.** `journal_entries.entry_type` is a plain indexed `String`
column with no enum/CHECK constraint (`backend/app/db/models.py:267`). The
Python member is nevertheless **required before any write**:
`JournalStore.append` coerces `str -> EntryType`
(`journal_store.py:84-86` — `EntryType(draft.entry_type)`), which raises
`ValueError` on an unknown string. Same coercion guards the list filter
(`backend/app/api/journal.py:72`), so `GET /v1/journal` filtering by
`entry_type=portfolio_health_analysis` works with zero API changes once the
member exists.

### 3.2 Entry shape — `build_finding_entry`

`backend/app/services/portfolio_health_journal.py`, pure function, no DB:

```python
from datetime import date
from uuid import UUID

from app.schemas.journal import EntryType, JournalEntryCreate

SECTION_KEYS = ("head", "f1", "f2", "f3", "f4", "f5")
FINDING_TAGS = ["portfolio_health", "cr136"]


def build_finding_entry(
    *,
    user_id: UUID,
    portfolio_id: UUID,
    as_of: str | date,                     # M06 carries the ISO string
    sections: dict[str, str],              # "head" + f1…f5 (the disclosure IS a section)
    context: dict,
    fired_rules: list[dict],
    rule_states: dict[str, str],
    engine_version: str,
    summary: str | None = None,            # first §F1 headline
    llm_used: bool = False,
    llm_rejected_reason: str | None = None,
) -> JournalEntryCreate:
```

> **AMENDED AT:R66, after M06/M07 shipped.** Four pins below were corrected by
> build/README's seam register (which overrides this doc) or by what M06 had
> already frozen. The mapper was NOT added as a second construction path — M06's
> inline dict literal was EXTRACTED into it, so there is one place that builds
> the artefact and one place that validates it:
>
> - **`reference_id=portfolio_id`, not `None`.** The register pins it (contract
>   5), and M07 reads Findings by portfolio — a null would make that a payload
>   scan.
> - **The disclosure lives at `payload["sections"]["head"]`**, not a sibling
>   `payload["disclosure"]`. Register-pinned; `SECTION_KEYS` is therefore
>   `("head", "f1"…"f5")`. The mobile renderer reads a top-level `disclosure`
>   as a fallback so an older entry still renders its caveats.
> - **`payload["rules_fired"]`**, not `"rules"` — the name M06 shipped, and the
>   register does not pin either.
> - **`summary` is the first §F1 headline**, not `None`. This doc's rationale
>   was the DEF150 class — a clipped markdown fragment in a list card — but §F1
>   headlines are plain sentences with no markup, so the concern does not bind,
>   and a card reading only "Portfolio Health — Finding 2026-08-02" tells the
>   user nothing about their own book.
> - `as_of` accepts an ISO string as well as a `date`: M06 carries it as a
>   string end to end, and an unconverted `date` would render
>   `datetime.date(2026, 8, 2)` into the title.
> - `dedupe_key` is new (M07 audit): `"<portfolio_id>:<as_of>"` under
>   `uq_journal_dedupe`, which is what stops two concurrent POSTs writing two
>   Findings.

Pinned output (each pin from Rev 4 "Journal storage plan" / the M08 brief,
except where marked M08-pin):

- `entry_type=EntryType.PORTFOLIO_HEALTH_ANALYSIS`
- `title=f"Portfolio Health — Finding {as_of}"` (e.g. `"Portfolio Health —
  Finding 2026-08-02"`) — **M06's pin** (M06 §3.7 "Title:"), which this doc
  originally contradicted with the shorter form. M06 shipped first and M08's
  job here was to EXTRACT its construction, so re-titling mid-extraction would
  have silently changed every future Finding's title away from the pin.
- `ticker=None` — structural consequence: `journal_context.py` fetches
  Bull/Bear lookback **by ticker** (`journal_context.py:48-50`), so Findings
  never leak into single-ticker Room prompts. No change needed there.
- `agents_involved=[]` (deterministic engine; agents arrive with CR137)
- `tags=list(FINDING_TAGS)` — exactly `["portfolio_health", "cr136"]`
- `summary=` the first §F1 headline (**amended**; the original `None` pin
  reasoned from a clipped MARKDOWN fragment, but §F1 headlines are plain
  sentences carrying no markup, and a card showing only the date tells the user
  nothing about their own book)
- `outcome=None`; `reference_id=portfolio_id` (**seam register**, which
  overrides this doc — M07 reads Findings by portfolio)
- `dedupe_key=f"{portfolio_id}:{as_of}"` (**added AT:R66, M07 audit**) — the
  `uq_journal_dedupe` value that stops two concurrent POSTs writing two
  Findings
- `payload=` exactly:

```python
{
    "portfolio_id": str(portfolio_id),
    "as_of": as_of.isoformat(),            # "YYYY-MM-DD"
    "engine_version": engine_version,       # "cr136.v1" (Rev 4 pin 8; M06 supplies it)
    "sections": {k: sections[k] for k in SECTION_KEYS},   # "head" IS the F19 disclosure
    "context": context,                     # stripped metric blocks (M06; insufficient already removed)
    "rules_fired": fired_rules,             # README contract-3 dicts, FIRED rules only, slots interpolated
    "rule_states": rule_states,             # {"R1": "fired"|"cleared", ...} — full hysteresis memory
    "llm_used": llm_used,
    "llm_rejected_reason": llm_rejected_reason,
}
```

These payload key names are the **freeze** for M07 (idempotency reads
`portfolio_id` + `as_of`), M09 and CR137 (render `disclosure` + `sections`).
Extra keys M06 may add ride along untouched; the pinned ones may not be
renamed.

Validation — degrade loudly (CR040), raise `ValueError` naming the field:
`sections` keys must EQUAL `set(SECTION_KEYS)` — missing AND unexpected both
raise, since the renderer walks a fixed order and a stray key would be stored
forever and shown to nobody — with non-empty `str` values throughout. `head` is
covered by that same check (F19: the archived artefact carries its own
disclosures forever — a Finding without them must never be stored).
`rule_states` values must be subsets of `{"fired", "cleared"}`.

### 3.3 Parity test (DEF210) — what actually must change

`backend/tests/unit/test_journal_entry_type_parity.py` needs **no edit**. Read
at HEAD: all three tests derive their sets, they hardcode no member list —
`test_from_wire_accepts_every_backend_entry_type` (:56) regex-extracts the
`case '...':` labels from `fromWire` in `journal.dart` and requires them to
cover `{e.value for e in EntryType}`; `test_dart_declares_no_wire_value_...`
(:68) does the reverse for the `wire` getter;
`test_unknown_entry_type_is_not_coerced_to_a_known_member` (:80) asserts no
`fromWire(...) ??` coercion exists.

What the test forces instead is **atomicity**: the backend member (§3.1) and
the Dart member + `wire` case + `fromWire` case (§3.5) must land in the **same
commit**, or `pytest backend/tests/unit/ -q` is red in between. Do not split
M08 into a backend commit and a mobile commit. The third test additionally
forbids "fixing" the mobile side with a `?? JournalEntryType.something`
default — the new mapping must return the member from a `case`, and unknown
strings must keep returning `null`.

### 3.4 Store reads for M07 (gating + hysteresis + idempotency)

Two narrow methods on `JournalStore` (`backend/app/services/journal_store.py`;
the row-access idiom lives there, and `_row_to_entry` is module-private to it).
Rev 4: hysteresis memory and idempotency *"share one read"*; trial accounting
*"reuses the journal as the counter"*. `list_for_user` cannot serve either —
it excludes soft-deleted rows (`:132`) and applies Floor Pass 30-day retention
(`:134-136`), which would both reset hysteresis for a Floor Pass user idle >30
days and let delete-to-reset-trial gaming work.

```python
def latest_portfolio_health_entry(
    self, user_id: UUID, portfolio_id: UUID | str,
) -> JournalEntry | None:
```
> **AMENDED AT:R66 (M07 build + audit).** Both reads INCLUDE soft-deleted rows,
> and `portfolio_health_stats` takes `(user_id, portfolio_id, *, now)` returning
> `(trial_findings_used, first_finding_at, daily_used)` — the daily cap is
> per-portfolio while the trial is per-user, so one read serves both. For the
> latest-entry read, "live only" was wrong in the same way retention was: a
> deleted Finding still counts against the budget and still carries the rule
> hysteresis state, because it is still something that happened. The caller
> distinguishes the two uses via `deleted_at` — the idempotent REPLAY requires
> it to be null, since returning a deleted entry answers "regenerate" with a
> journal id pointing at a row the user cannot open.

Newest **live** (`deleted_at IS NULL`) row with
`entry_type == EntryType.PORTFOLIO_HEALTH_ANALYSIS.value`, ordered
`created_at` desc, first whose `payload["portfolio_id"] == str(portfolio_id)`
(payload filter in Python — no JSONB operator dependence, sqlite-fixture
compatible). **No plan/retention filter.** Serves both the `(portfolio_id,
as_of)` idempotency check and the `rule_states` read-back (compare
`payload["as_of"]` / read `payload["rule_states"]` — M07/M05 logic, not
M08's). Series never spans a reset: `reset_portfolio` is destroy-and-recreate
(`sim_engine.py:394-403`), so a new `portfolio_id` naturally starts with no
prior entry ⇒ hysteresis initial state cleared.

```python
def portfolio_health_stats(self, user_id: UUID) -> tuple[int, datetime | None]:
```
Count of ALL `portfolio_health_analysis` rows for the user **including
soft-deleted** (Rev 4 pin: *"soft-deleted rows included"*), plus the earliest
`created_at` (`None` when count is 0). M07's trial window (14 days from first
Finding) and budget (7 Findings) both read from this.

### 3.5 Mobile model — `mobile/lib/models/journal.dart`

Three edits, mirroring the file's existing shape exactly:

1. Enum (`:14`): add `portfolioHealthAnalysis,` after `dailyChallenge`.
2. `wire` getter (`:36-37` region): add
   `case JournalEntryType.portfolioHealthAnalysis: return 'portfolio_health_analysis';`
3. `fromWire` (`:58-59` region): add
   `case 'portfolio_health_analysis': return JournalEntryType.portfolioHealthAnalysis;`

**Preserve the DEF210 design** (`:86-91` doc comment + `:113`): `entryType`
stays `JournalEntryType?`, `fromJson` stays
`JournalEntryTypeJson.fromWire(...)` with **no** `??` fallback — unknown wire
values stay `null` and route to the generic UI. The parity test (§3.3) enforces
this from the backend suite.

### 3.6 Journal list card — `journal_screen.dart`

Both switches are exhaustive with `case null`, so `flutter analyze` fails until
the new cases exist (SCREEN_DESIGNS: *"take that compile error as the
checklist"*):

- `_accent` (`:430-453`): `case JournalEntryType.portfolioHealthAnalysis:
  return AmiColors.hexBlue;` — hexBlue is the Portfolio Health feature accent,
  *deliberately not amber* (SCREEN_DESIGNS:62 — amber already means
  degraded/partial in this app). Sharing hexBlue with roomRun/oneOnOne is
  precedented (`:433`/`:447`); the badge text disambiguates.
- `_label` (`:455-478`): `case JournalEntryType.portfolioHealthAnalysis:
  return l.journalEntryTypeHealth;`

The filter-chip row (`filtersFor`, `:32-45`) is NOT extended here — M09 owns
the journal-UI surface and decides whether Findings get a chip.

### 3.7 l10n — one new key, three files

`app_en.arb`, beside the other `journalEntryType*` keys (`:437-449` region) —
new EN string, **flagged `retranslate:[ar,ms]`**:

```json
"journalEntryTypeHealth": "HEALTH",
"@journalEntryTypeHealth": {
    "description": "CR136 — Journal entry-card badge for a portfolio_health_analysis entry (a stored Portfolio Health Finding). Short all-caps badge like ROOM / TRADE. NEW key, needs ar/ms translation. retranslate:[ar,ms]"
}
```

Per the DEF210 convention (`journalEntryTypeUnknown`: `app_ar.arb:96`,
`app_ms.arb:10` carry the English value verbatim, no `@` metadata outside the
template): add `"journalEntryTypeHealth": "HEALTH",` to **both** `app_ar.arb`
and `app_ms.arb` as placeholders — `mobile/test/l10n_key_parity_test.dart`
(DEF137) fails the suite if any locale lacks the key. The ms-file header
documents the auto-translate flow that later replaces placeholders.

This is M08's only new user-visible string; it contains no copy where the
AMI-by-name rule could bind. All Finding copy is stored server-side (M06).

### 3.8 Detail rendering — `finding_sections.dart` + the branch

New widget, `mobile/lib/widgets/journal/finding_sections.dart`:

```dart
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/room/room_board.dart';   // agentMarkdownStyle (:1198)
import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

class FindingSections extends StatelessWidget {
  const FindingSections({super.key, required this.payload});
  final Map<String, dynamic> payload;

  static const sectionOrder = ['f1', 'f2', 'f3', 'f4', 'f5'];

  /// True only when the stored payload carries what F19 requires: a non-empty
  /// disclosure AND a sections map. Anything less renders via the generic
  /// payload dump instead — degrade loudly, never a disclosure-less report.
  static bool isRenderable(Map<String, dynamic> payload) =>
      payload['disclosure'] is String &&
      (payload['disclosure'] as String).trim().isNotEmpty &&
      payload['sections'] is Map;
  ...
}
```

`build`: a `Column(crossAxisAlignment: CrossAxisAlignment.start)` emitting, in
this order:

1. **The head disclosure block FIRST** (F19 — Rev 4 reversed the
   foot-of-report placement): the `payload['disclosure']` markdown inside a
   recessed container (`AmiColors.slate800` fill, 1px `AmiColors.slate700`
   border, `AmiRadii.card`, `AmiSpacing.s` padding — the `_Block`/`_KVBox`
   chrome idiom from `journal_detail_screen.dart:542-551`), rendered with
   `MarkdownBody(data: ..., shrinkWrap: true, styleSheet:
   agentMarkdownStyle(AmiColors.textMed))`.
2. Then `sections[key]` for each of `sectionOrder` in order, each a
   `MarkdownBody` with the same `agentMarkdownStyle(AmiColors.textMed)`
   stylesheet (`room_board.dart:1198` — the shared helper the Room transcript
   uses at `room_transcript_rows.dart:340/:348/:452`), separated by
   `SizedBox(height: AmiSpacing.s)`. A missing/empty/non-`String` section is
   skipped, not substituted — render stored content only, **never
   regenerate**, no client-side recomputation of any number.

Branch in `_PayloadBlock.build` (`journal_detail_screen.dart`), inserted
before the final `else` at `:342`, following the `roomRun` early-return
precedent (`:309-327`):

```dart
} else if (entryType == JournalEntryType.portfolioHealthAnalysis &&
    FindingSections.isRenderable(payload)) {
  return FindingSections(payload: payload);
}
```

A malformed payload (missing disclosure or sections) falls through to the
existing generic key/value dump (`:342-346`) — visible raw data, never a blank
screen and never a disclosure-less Finding. Import the new widget file;
`journal_detail_screen.dart` needs no `flutter_markdown_plus` import of its
own. `flutter_markdown_plus: ^1.0.3` is already a dependency
(`mobile/pubspec.yaml:74`).

Sweep checks that pass without edits (verified): `showsAgentPills`
(`journal_detail_screen.dart:219-220`) defaults new types to SHOW —
`agents_involved` is `[]` so nothing draws; the CR111/DEF150 enum sweeps in
`mobile/test/widgets/journal_replay_chrome_test.dart:70-90` and
`journal_reason_placement_test.dart:112` iterate `values` generically.

### 3.9 Old-client degradation (verified, acceptable interim)

A client built before M08 has no `portfolio_health_analysis` case:
`fromWire` returns `null` (DEF210 design), the list card renders the slate
badge `UNKNOWN` (`journal_screen.dart:450-451` + `:475-476`), and the detail
screen falls into the generic payload dump (`:342-346`) — the raw payload
values as bare text, including the disclosure text, ugly but visible and
honestly labelled. No blank body, no impersonated type. This is the accepted
interim until stores ship the M08+ build; no server-side version gate is
added.

## 4. Out of scope for this module

- **Finding generation and content** — M06 owns the renderer, validator,
  deterministic templates, and the disclosure block's wording. M08 stores what
  M06 produced, verbatim.
- **Gate/idempotency/hysteresis ENFORCEMENT** — M07 owns the
  `POST .../finding` route, trial policy, daily cap, and the check-before-
  insert logic; M05 owns interpreting `rule_states`. M08 only provides the
  reads (§3.4) and the payload keys they consume.
- **Health card, Screen-21 Finding view, filter chip, golden tests of card
  states, gate CTA states** — M09 (which reuses `FindingSections`: one
  component, two hosts, per SCREEN_DESIGNS §17+).
- **Backfill** (M10), **promotion/E2E** (M11), **CR137** Portfolio Room.
- **`journal_context.py`** — untouched; `ticker=None` keeps Findings out of
  the Bull/Bear per-ticker lookback structurally (§3.2).
- No new Settings, so no `docker-compose.yml` / config-parity work here (M07).

## 5. Tests

**Backend — `backend/tests/unit/test_portfolio_health_journal.py`** (idioms
from `test_journal_store.py`: sqlite tempfile fixture, `_backdate_for_test`
helper at `journal_store.py`):

1. `EntryType.PORTFOLIO_HEALTH_ANALYSIS.value == "portfolio_health_analysis"`.
2. **Append round-trip with the new type**: `build_finding_entry(...)` →
   `JournalStore().append(...)` → `list_for_user(user_id,
   entry_type=EntryType.PORTFOLIO_HEALTH_ANALYSIS)` returns it; stored
   `entry_type` string equals `"portfolio_health_analysis"`; payload deep-equal
   after the JSONB round-trip (sections + disclosure + rule_states intact).
3. Raw-string append coerces (`entry_type="portfolio_health_analysis"` passes
   the `journal_store.py:84-86` path); unknown string
   (`"portfolio_health_analysis_v2"`) still raises — the guard is intact.
4. **Entry shape pins** (**amended AT:R66** to the shipped shape): title
   `"Portfolio Health — Finding 2026-08-02"` for `as_of=date(2026, 8, 2)`;
   `ticker is None`; `agents_involved == []`;
   `tags == ["portfolio_health", "cr136"]`; `summary` passes through (the first
   §F1 headline); `outcome is None`; `reference_id == portfolio_id`;
   `dedupe_key == f"{portfolio_id}:{as_of}"`; payload keys exactly
   `{portfolio_id, as_of, engine_version, sections, context, rules_fired,
   rule_states, llm_used, llm_rejected_reason}`; `sections` keys exactly
   `{head, f1..f5}`.
5. **Validation**: missing `"f3"` → `ValueError`; empty `disclosure_md` →
   `ValueError`; `rule_states={"R1": "armed"}` → `ValueError`.
6. **`latest_portfolio_health_entry`** (**amended AT:R66**): two portfolios
   interleaved → returns the newest for the queried `portfolio_id` only; a
   soft-deleted newest IS returned, carrying `deleted_at` so the caller can
   refuse to replay it while still reading its `rule_states`; an entry
   backdated 31 days via `_backdate_for_test` is STILL returned (no Floor Pass
   retention — the hysteresis-memory property); no entries → `None`.
7. **`portfolio_health_stats`** (**amended AT:R66** — 3-tuple, per-portfolio
   daily counter): `(0, None, 0)` when empty; count includes a soft-deleted row
   (delete-to-reset-trial must not work); `first_at` is the earliest
   `created_at`; `daily_used` counts only today's rows for THIS portfolio, on a
   UTC day boundary.
8. `test_journal_entry_type_parity.py` — run unmodified; green proves the Dart
   half landed in the same tree (§3.3).

**Mobile — `mobile/test/models/journal_entry_type_test.dart`**:

1. `JournalEntryTypeJson.fromWire('portfolio_health_analysis') ==
   JournalEntryType.portfolioHealthAnalysis`.
2. Sweep: for every `JournalEntryType.values` member,
   `fromWire(t.wire) == t` (round-trip; auto-covers future members).
3. DEF210 preserved: `fromWire('never_heard_of_it') == null`, and
   `JournalEntry.fromJson` with that wire value yields `entryType == null`.

**Mobile — `mobile/test/widgets/finding_sections_test.dart`** (host idiom from
`journal_replay_chrome_test.dart:46-50` — plain `MaterialApp` +
`AppLocalizations` delegates; no Riverpod needed since `FindingSections` is
payload-pure). Fixture payload: distinct marker strings, e.g. `disclosure:
"Educational simulation. Not investment advice. DISCLOSURE-MARK"`, `sections:
{f1: "F1-MARK ...", ..., f5: "F5-MARK ..."}`:

1. `isRenderable` true on the fixture; false when `disclosure` missing, empty,
   or whitespace; false when `sections` missing.
2. **Disclosure renders before §F1** (the brief's required widget test): pump
   `FindingSections(payload: fixture)`; collect
   `tester.widgetList<MarkdownBody>(find.byType(MarkdownBody)).toList()`;
   assert 6 bodies, `bodies[0].data` == the disclosure string,
   `bodies[1].data` == the f1 string, and `bodies[1..5]` follow
   `sectionOrder` — order in the `Column` is the structural guarantee.
3. A payload with `f3` absent renders 5 bodies (skipped, not substituted) and
   the surviving order is still disclosure, f1, f2, f4, f5.

## 6. Acceptance

Reviewer checklist (Mac is pure editor — nothing live needed):

- [ ] `pytest backend/tests/unit/test_portfolio_health_journal.py
      backend/tests/unit/test_journal_entry_type_parity.py -q` → green.
- [ ] `pytest backend/tests/unit/ -q` → green (no collateral).
- [ ] `cd mobile && flutter analyze` → clean (proves the two exhaustive
      switches in `journal_screen.dart` gained their cases).
- [ ] `cd mobile && flutter test` → green, including
      `test/l10n_key_parity_test.dart` (proves ar/ms placeholder keys exist)
      and the two new test files.
- [ ] `grep -c "portfolio_health_analysis" mobile/lib/models/journal.dart`
      → `2` (wire + fromWire).
- [ ] `grep -n "fromWire([^)]*)\s*??" mobile/lib/models/journal.dart` → no
      match (DEF210 anti-coercion preserved; the parity test also enforces it).
- [ ] `grep -n "journalEntryTypeHealth" mobile/lib/l10n/app_en.arb
      mobile/lib/l10n/app_ar.arb mobile/lib/l10n/app_ms.arb` → 1+ hit per
      file; the EN `@` description carries `retranslate:[ar,ms]`.
- [ ] `grep -n "isRenderable" mobile/lib/screens/journal/journal_detail_screen.dart`
      → the branch guards on it (malformed → generic dump, not blank).
- [ ] Single commit spans backend enum + Dart model (§3.3 atomicity), tagged
      `(AT:R<N> CR136)`, pathspec-committed:
      `git commit -m "feat(journal): portfolio_health_analysis entry type,
      Finding storage + mobile render (AT:R<N> CR136)" -- <the files in §2>`.

## 7. Hand-off

After M08, the following exist and may be assumed:

- **M07** may call `build_finding_entry(...)` (§3.2 signature) to construct
  the `JournalEntryCreate` from M06's artefact and
  `get_journal_store().append(...)` it; may call
  `latest_portfolio_health_entry(user_id, portfolio_id)` for the shared
  idempotency + `rule_states` read (compare `payload["as_of"]`, read
  `payload["rule_states"]`, and check `deleted_at is None` before replaying one
  to a client), and `portfolio_health_stats(user_id, portfolio_id, *, now) ->
  (trial_findings_used, first_finding_at, daily_used)` for trial AND daily-cap
  accounting — **corrected AT:R66**; the single-argument form in the original
  draft does not exist. **Caution:** do NOT use `list_for_user` for either — its
  retention + soft-delete filters break both semantics (§3.4).
- **M05** may rely on `rule_states` round-tripping the journal payload
  verbatim, and on a fresh `portfolio_id` returning `None` from the read
  (hysteresis initial state = cleared).
- **M09** may reuse `FindingSections` (public widget, payload-pure) as the
  Screen-21 section renderer — one component, two hosts — and may add a
  journal filter chip for the type if its designs call for one; the
  `journalEntryTypeHealth` badge key and hexBlue accent are in place.
- **Wire**: `entry_type == "portfolio_health_analysis"` is accepted by
  `GET /v1/journal`'s filter and emitted in list/detail responses; old clients
  degrade to the slate UNKNOWN card + generic payload dump (§3.9).
- **i18n lane**: `journalEntryTypeHealth` ("HEALTH") is flagged
  `retranslate:[ar,ms]` with placeholder entries in both locale files.
