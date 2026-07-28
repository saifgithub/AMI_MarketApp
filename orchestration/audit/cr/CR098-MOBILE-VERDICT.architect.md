<!-- architect bridge — track R. CR052 / orchestration/audit/PROTOCOL.md. -->
# CR098-MOBILE-VERDICT — architect bridge

ITEM: CR098-MOBILE-VERDICT
INSTANCE: architect (track R) — built directly, no coder lane
GATE: independent
SCOPE: cr
BRANCH: `lane/CR098-MOBILE-VERDICT.coder.mobile` @ `89d3f95`
WORKTREE: `.claude/worktrees/coder.mobile-CR098-VERDICT`
SUBMITTED: round 1

---

# Round 1

The last CR098 lane. Two commits, risk-ordered: `19f9acb` parse layer, `89d3f95` render layer.

## Read this first — the lane's central premise turned out to be false

The assign opens: *"This half is the higher-risk of the two: it introduces an enum value that makes
previously-non-null fields null… **This is the crash risk.** Any non-null assumption in the verdict
card — a `!`, a non-nullable field, a `.toStringAsFixed()` on a null double — throws at runtime."*

**It does not throw.** Acceptance #2 required me to measure current behaviour before changing
anything, and that is the single most useful number here, so it went first:

```
PROBE parse:  action=NO_VERDICT size=null entry=null target=null stop=null horizon=null
PROBE render: exception=null
PROBE texts:  [… VERDICT — NO_VERDICT, No verdict — and that is deliberate. …]
```

Two independent reasons it was already safe, both pre-existing and neither deliberate:

1. `RoomVerdict`'s level fields were **already** `double?`/`int?` and parsed with `as num?`.
2. Every `_MetricRow` sits behind `if (isApprove)`, so a `NO_VERDICT` card never reaches
   `.toStringAsFixed()` at all.

So acceptance 3 and 4 were **already satisfied on `main`** — by accident, held by nothing. I have
pinned them with tests rather than claiming to have fixed them. **If you audit only one thing here,
audit that claim**: `git stash` my test file onto `main` and confirm criteria 3–4 pass there too.

**What is actually broken is the thing the assign did not scope**, and CR106's spec caught it
independently: *"`NO_VERDICT` (today amber, i.e. reads as a rejection)."* Confirmed by measurement —
`accent` falls through to `hexAmber` and the icon to `Icons.cancel`. The PM refuses to price a trade
without a market read, and the card renders that refusal in the reject treatment. **The lane's real
defect is semantic, not a crash.**

## What changed

### Parse layer — `19f9acb`, `models/room.dart`

- `opinionsNotIncluded` (D3) and `isNoVerdict` added; the `action` doc comment now states the enum
  **grows** rather than listing four values as though closed.
- `violations` **and** `opinions_not_included` move from `cast<String>()` to `whereType<String>()`.
  `cast` defers the type error to first read — i.e. into `build()` — so one non-String on the wire
  throws while rendering rather than at the parse boundary. Same class as your CR098-MOBILE-LIVE
  round-2 MINOR; I went looking for it after that.

### Render layer — `89d3f95`

| Change | Why |
|---|---|
| `NO_VERDICT` takes PASS's neutral treatment (slate accent, `pause_circle_outline`) | The actual defect. Amber + `Icons.cancel` says "turned down". |
| `NO_VERDICT` heading renders **`NO VERDICT`**, not the wire token | `NO_VERDICT` with the underscore is not user-facing copy. Unknown actions still render **raw** rather than crashing (#9). |
| `opinions_not_included` closing disclosure on **every** action (D3) | An `APPROVE` reached without Social must still disclose it. Gating on `NO_VERDICT` is the inversion D3 names — **M2 proves the gate would ship silently**. |
| Empty list ⇒ **nothing** (D4) | Every existing user sees this card until a threshold is set. |
| Unresolvable agent id renders **as itself** | `agentById` falls back to the **Concierge**, so an unknown id would name the wrong analyst as absent — a confident lie. **M4.** |
| App-chrome CTA under a `Divider`, outside the reason block | D2a: the PM declines on professional grounds and never sells. |

### One change outside the declared HOT-FILES — disclosed, not buried

`share_service.dart`, **one call site**: `shareVerdict`'s accent mirrors the card's exactly, so
without a neutral flag the **shared image** renders `NO_VERDICT` in amber. The card on screen would
say one thing and the image the user posts to a group chat another. Added `bool isNeutral = false`
(existing callers unaffected) and passed `verdict.isNoVerdict` from the card.

**HOT-FILES named only the card and `api_client.dart`.** I judged same-defect-same-fix and took it;
say if you read it as scope creep. It is two lines and trivially revertible.

## Measured — round 1, foreground, this worktree

| Check | Result |
|---|---|
| Full `flutter test` | **143/143** (`main` = 128, +15 new) |
| `flutter analyze --no-fatal-infos` | **exit 0**, exactly the 5 pre-existing infos the assign predicted |
| Probe before any edit (#2) | **renders, does not throw** — output above |
| Tree after all 5 mutations reverted | `git status --porcelain` **empty**, 143 restored |

### Mutation proof — 5, each applied physically, each RED at exactly one test, each reverted

| | Mutation | Result |
|---|---|---|
| **M1** | `neutral = isPass \|\| isNoVerdict` → `isPass` (restore the amber reject accent) | **RED** — *neutral accent + neutral icon* |
| **M2** | Gate the disclosure on `isNoVerdict` — **the D3 inversion** | **RED** — *renders on an APPROVE with Social withheld* |
| **M3** | Raw `verdict.action` back into the heading | **RED** — *the raw wire enum never reaches the user* |
| **M4** | `_analystLabel` → `agentById(id).displayName` | **RED** — *an unresolvable agent id renders as itself* |
| **M5** | `whereType` → `cast` on `opinionsNotIncluded` | **RED** — *a malformed opinions list does not take down the card* |

M2 is the one I would attack: it is the DEF059-class inversion, it is invisible in the common case,
and nothing but that test holds it.

## What I want you to attack

1. **The "already safe" claim.** It is the load-bearing statement in this bridge. Run criteria 3–4
   against `main` and tell me if I am wrong.
2. **`_blockingAnalystId`.** With Market in the list it returns Market; otherwise the first entry;
   with an empty list it returns `market_analyst` as a constant — but that branch is unreachable,
   since the CTA only renders under `isNoVerdict` and the backend always fills the list there. I
   could not construct a live payload that reaches the fallback. If you can, it is a finding.
3. **`pause_circle_outline` as the neutral icon.** A judgement call, not a measurement. PASS keeps
   `remove_circle_outline`; I wanted NO_VERDICT distinguishable from PASS while still not reading as
   a rejection. Score it if you disagree.
4. **The D4 "byte-identical" test.** I assert an empty list renders the same text set as the key
   being **absent from the wire entirely** — not a true byte-diff against pre-change `main`. That is
   weaker than the criterion's wording. Deliberate, and I am flagging it rather than hoping.

## What I did NOT verify

- **Nothing on a device or against melehost.** Promotion hold active; unit + widget level only.
  Nobody has seen this render on a phone.
- **No live `NO_VERDICT` run.** Every payload here is hand-built from `room_runner.py`'s
  `_assemble_no_verdict`, read at the source. I did not convene a real Room with Market withheld.
- **`ar` / `ms` for the 4 new strings** — `roomVerdictActionNoVerdict`,
  `roomVerdictOpinionsHeading`, `roomVerdictOpinionsNote`, `roomVerdictIncludeAnalystCta`. Generated
  files carry EN in all three locales. **This lane adds 4 keys to the 24 already filed as DEF137**;
  the packet is at `docs/forward_planning/CR083_language_manager_ar_ms_translation_delivery/DEF137_missing_keys_packet.md`.
  Deliberately no list-grammar placeholder — names render as bullets so no locale has to solve
  "A, B and C".
- **The share card's rendered image.** I changed the accent input; I did not capture and inspect a
  PNG.

## Definition of Done

Rendered although `AMI_TRADE_BINDINGS.md` gap-fill 7 waives it — and aware that a false `N/A` in a
table that IS rendered is still a MAJOR under that same waiver.

| Row | Disposition |
|---|---|
| **Scope** | CR098 scope item 8, part 2 of 2: the terminal verdict card. 5 files, 2 commits. Verdict-card surface only — the streaming surface was `CR098-MOBILE-LIVE`, merged at `e679dc4`. |
| **Tests** | `flutter test` **143/143**; 15 new, one per acceptance criterion, all driving the real `RoomVerdict.fromJson` and the real `RoomScreen`. 5 mutations, all RED at exactly the intended test, all reverted with a clean tree. |
| **Manual verification** | **None, and it is not available:** `main` is under an active promotion hold (`infra/PROMOTION_HOLD.md`, CR090-ROOM) and this lane is unmerged. `NEEDS-DEVICE-CHECK`, same as the sibling lane. |
| **Docs** | This bridge + the lane hand-off. No spec edit — `CR098_room_analyst_pullback.md` §"Amendment 2" and §"professional discipline" were the input, unchanged. The 4 new ARB keys carry `description` metadata naming their CR and their constraint. |
| **Commit tag** | `19f9acb` + `89d3f95`, both `(AT:R65 CR098)`. |
| **Register** | `CR098.row.md` stays `started` — correct until this lane is audited and integrated, at which point the umbrella can close. Row is `AT:R59`-owned; not edited by me, no status change is due yet. |
| **Scope discipline** | One deliberate step outside HOT-FILES: `share_service.dart`, 2 lines, disclosed above with the reasoning. Nothing else touched. Two things found and **not** folded in: the duplicate `_resetDateStr` already present twice in `room_screen.dart` (I added a third rather than refactor someone else's), and CR106's overlap on this same surface. |
