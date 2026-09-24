# CR232 — Persistent shell chrome across every pushed page

## What

Every post-onboarding screen in the app now keeps the bottom nav, the (reserved) ad slot,
and the ticker tape visible — including full pages pushed from inside a tab and the
full-screen chart. The mechanism: each `AmiTab` gets its own nested `Navigator`
(`_TabNavigator` in `home_shell.dart`), so `Navigator.of(context).push(...)` — unchanged at
every call site — now lands inside that tab's `IndexedStack` cell, below the persistent
chrome, instead of on the single root `Navigator` that used to cover the whole shell.

The top-right `Icons.close` pattern this forced onto ~13 screens is retired for full pages:
`AmiScreenHeader`'s back chevron (+ iOS edge-swipe, which nested Navigators support for
free) is the one exit affordance. `Icons.close` remains only for genuinely inline
dismissals (a chip's delete glyph, an ad card's own dismiss, a notice banner's own X) —
never a page's own way out.

The two trade tickets (`TradeTicketSheet`, `GamesTradeTicketScreen`) become full pages
pushed inside the active tab, with a back chevron and a "Cancel" text action, replacing
the modal-sheet-with-an-X pattern DEF415 had just added a close button to.

## Why

Saiful, 2026-09-24: *"Some pages are simply using an 'X' to exit (top right) — obscure and
not in line with the app's aesthetics. The bottom menu, the ad, and the ticker tape should
always be on every screen and page, with a more elegant exit than the X."*

**Root cause, verified in `home_shell.dart` before this CR:** the bottom nav (`HexBottomNav`)
and `TickerTape` lived in `HomeShell`'s own `Scaffold.bottomNavigationBar` — below the
`body`'s `IndexedStack` in the same Scaffold, but *above* nothing a pushed route could get
under. Every `Navigator.of(context).push` / `showModalBottomSheet` in the app (~56 push
sites, ~25 sheet sites, at the time this was scoped) resolved to the single ROOT
`Navigator`, i.e. `MaterialApp`'s own — which sits *above* `HomeShell` in the widget tree.
A route pushed there covers `HomeShell`'s entire `Scaffold`, chrome included, and had
nothing to pop back to except an exit control it had to invent for itself. That is exactly
P36 in `failure_patterns.md`: ~13 independent `Icons.close` sightings, each locally
reasonable, sharing one structural cause a per-screen review could not see.

**The fix is structural, not a convention.** `Navigator.of(context)` already resolves to
the *nearest* ancestor Navigator — that's the whole mechanism nested navigation exploits.
Wrapping each tab's pane in its own `Navigator` (`_TabNavigator`) means a push from inside
that pane finds the tab's own Navigator first, landing the pushed page in the
`IndexedStack` cell rather than covering it. No call-site changes were needed for ordinary
pushes; only the widget tree changed.

## Saiful's rulings (verbatim)

1. Chrome order bottom-to-top: **nav / ad slot / ticker tape** (CR226 spec order — nav on
   top, then ad, then tape, then home indicator). The ad slot is CR226's; it is not built
   yet, so this CR reserves the slot as a zero-height placeholder
   (`widgets/ads/shell_banner_slot.dart`) so no layout change is visible until CR226 fills
   it. AdMob itself is out of scope here.
2. Nav + ad + tape visible on every post-onboarding page, including pushed detail pages and
   the full-screen chart. Exceptions ONLY: (a) the chrome hides while the software keyboard
   is open; (b) onboarding / Concierge (pre-shell) is unchanged.
3. Trade tickets (`TradeTicketSheet`, `GamesTradeTicketScreen`) become full pages pushed
   inside the tab, with the back chevron and a "Cancel" text action — not modal sheets.
4. Exit affordance everywhere a full page is pushed: `AmiScreenHeader` with a back chevron
   (hex-cyan, AMI style) + parent label where practical, plus iOS edge-swipe back. Remove
   the top-right X on full pages. KEEP `Icons.close` only for dismissing small inline cards
   (ad cards, `floor_reaction_card`, journal/brief inline dismissals) and chip delete icons.
5. Tapping the already-selected tab pops that tab's stack to its root. Android system back
   pops within the active tab first.

## Scope

Mobile-only. Supersedes DEF415's close-button approach on the two trade tickets (commit
`f430764c`, one commit prior on this branch) — those close buttons are removed in favour of
the page conversion this CR does instead.

**CR226 depends on this CR's slot.** The banner slot this CR reserves
(`ShellBannerSlot`, currently `SizedBox.shrink()`) is where CR226's adaptive AdMob banner
will render; CR226 should not need to touch `home_shell.dart`'s Column structure again,
only replace what `ShellBannerSlot` builds.

**DEF419 note (flagged by the Architect mid-build):** DEF419 (mandate check must use the
destination account — Alpaca vs AMI sim) will modify `trade_ticket_sheet.dart`'s
destination/preview logic (`_submitAlpacaOnly`, the `TradeDestination.both` branch) after
this branch merges. This CR does not touch that logic at all — `_submit`, `_submitAlpacaOnly`,
`_placeAlpacaOrder`, `_reportOrderLog` and the destination selector are byte-for-byte
unchanged except for their surrounding container (Padding/SingleChildScrollView → Scaffold/
SafeArea/Column/Expanded/SingleChildScrollView). The diff DEF419 lands against this branch
should be clean.

### In scope

- `HomeShell` restructured: one `GlobalKey<NavigatorState>` per `AmiTab`, each tab's pane
  wrapped in its own `Navigator` (`_TabNavigator`), the `IndexedStack` unchanged otherwise
  (tab state preserved exactly as before). Chrome (`HexBottomNav` / `ShellBannerSlot` /
  `TickerTape`) stays a sibling of the `IndexedStack` in `Scaffold.bottomNavigationBar`,
  hidden when `MediaQuery.viewInsetsOf(context).bottom > 0` (keyboard open).
  `PopScope(canPop: false)` + `_onWillPop` routes Android system back through the active
  tab's own Navigator first (rule 5).
- Re-tapping the active tab (`_onNavTap`) pops that tab's Navigator to its first route
  (rule 5) instead of doing nothing; switching to a *different* tab is unaffected (never
  touches the other tab's stack).
- `TradeTicketSheet` and `GamesTradeTicketScreen`: `show()` now `Navigator.push`es a
  `MaterialPageRoute` instead of `showModalBottomSheet`. Both gain `AmiScreenHeader`
  (back chevron + "Cancel" `TextButton`, both popping the same Navigator) and lose their
  `showModalBottomSheet`-era sheet chrome (backgroundColor/shape/isScrollControlled,
  `sheetBottomInset`). Both wrap `body` in `SafeArea` (matching every other screen's
  established pattern — NOT `Scaffold.appBar`, which is not `SafeArea`'d) and a
  `GestureDetector` that unfocuses on tap, so the iOS numeric keypad (no return key on
  quantity/stop/target/limit/trigger fields) has a way to close. The scroll view's
  `keyboardDismissBehavior: onDrag` gives a second dismiss path for fields below the fold.
- `AmiScreenHeader` gains a `Semantics(identifier: ExitIds.navBack)` wrapper on its back
  chevron (was unidentified before this CR).
- `mobile/lib/qa/semantics_ids.dart` gains `ExitIds` (`navBack`, `tradeTicketCancel`).
- Three genuinely full-page `Icons.close` sites converted to the back-chevron pattern:
  `alpaca_connect_screen.dart` (kept `pop(false)` semantics for the caller's existing
  `result == true` contract), `legal_screen.dart`, `chart_fullscreen_screen.dart`.
- All 23 `showModalBottomSheet` call sites gained `useRootNavigator: false` — a
  one-line addition per site — so a sheet ties to the caller's nearest (tab) Navigator
  and its `Overlay` sits below the persistent chrome rather than above it, instead of the
  default `useRootNavigator: true`, which would tie it to the app's single root Overlay.
  None of these 23 sites converted to full pages: all are genuinely transient/modal
  (tour intros, confirmations, pickers, disclosures, the bug-report form).
- `mobile/lib/widgets/ads/shell_banner_slot.dart` (new) — the CR226 reservation, currently
  `SizedBox.shrink()`.
- `docs/initial_specs/08_tech/failure_patterns.md` — new entry **P36** (the guard class:
  N independent screens growing the same workaround because the mechanism that would have
  made it unnecessary never reached them).

### Site classification (final counts)

| Class | Count | Treatment |
|---|---|---|
| `Navigator.of(context).push(...)` sites in `lib/` | 60 | Unchanged — nested-Navigator resolution is automatic. (Count includes the two trade tickets' own `show()`; the pre-CR baseline noted in the brief was ~56.) |
| `showModalBottomSheet` sites | 23 | Kept modal; `useRootNavigator: false` added to every site (one-line, uniform). |
| `rootNavigator: true` sites | 1 (`bug_report_sheet.dart`) | Not a page push — fetches the root `Overlay`'s context for a toast after the sheet pops. Unrelated to this CR, left as-is. |
| Trade tickets converted sheet → page | 2 | `TradeTicketSheet`, `GamesTradeTicketScreen`. |
| `Icons.close` sites converted to back chevron | 3 | `alpaca_connect_screen.dart`, `legal_screen.dart`, `chart_fullscreen_screen.dart`. |
| `Icons.close` sites kept (inline dismiss / chip delete — rule 4 exception) | 9 | `trade_ticket_sheet.dart` ("NO AI VERDICT" advisory dismiss), `journal_screen.dart` (search-field clear), `agent/brief_screen.dart` (refusal notice dismiss), `sim/ticker_detail_screen.dart` (price-alert banner dismiss), `settings/ticker_rules_section.dart` (chip delete), `feedback/bug_report_sheet.dart` (the sheet's OWN close — it is a modal sheet with a drag handle, not a page — plus an inline "remove attached photo" control), `widgets/ads/house_ad_card.dart`, `widgets/ads/admob_native_card.dart`, `widgets/floor/floor_reaction_card.dart`. |

Enforced going forward by `mobile/test/exit_affordance_structural_test.dart` — walks
`lib/screens/` and `lib/widgets/`, fails if any file outside the 9-file allowlist above
contains an `Icon(Icons.close` construction (a regex, not a bare string match, so doc
comments mentioning `Icons.close` — `home_shell.dart`, `qa/semantics_ids.dart` — don't
trip it). A second test in the same file asserts the allowlist has no stale entries.

## i18n

No new user-visible strings were needed. The trade tickets' "Cancel" action reuses the
existing shared `actionCancel` ARB string ("CANCEL" — "Generic cancel button in dialogs
and sheets"), already used identically in three other screens
(`brief_history_screen.dart`, `portfolio_screen.dart`, `confirm_restart_onboarding.dart`).
No retranslation flag needed — the string and its meaning are unchanged, only a fourth/
fifth call site.

## Acceptance

- `flutter analyze` → 0 errors (11 pre-existing `info`-level lints, unchanged from
  baseline).
- `flutter test` → all green (1499 tests).
- `home_shell_test.dart` covers: a pushed page inside a tab still shows the bottom nav +
  ticker tape; re-tapping the active tab pops to root; the software keyboard hides the
  chrome and it returns on dismiss; the trade ticket opens as a page with back + Cancel
  and no `Icons.close`; the trade ticket header sits below the top safe-area inset
  (regression test for the TestFlight +108 status-bar overlap); tapping the trade ticket
  body dismisses the keyboard (regression test for the +108 stuck-numeric-keypad report).
  All six were mutation-tested (each assertion was verified to fail when the underlying
  fix was reverted, then the revert was undone).
- `exit_affordance_structural_test.dart` — the P36 guard — mutation-tested the same way
  (a fake file constructing `Icons.close` was injected and confirmed caught, then removed).
- DEF190's existing regression test ("Review in Journal" switches tabs rather than pushing
  a route) still passes unmodified — the `activeTabProvider` mechanism it guards is
  untouched by this CR.

## Follow-ups this CR does NOT do

- CR226's actual AdMob banner — this CR only reserves the slot.
- DEF419's destination-aware mandate check — explicitly left for the next diff (see Scope
  note above).
- No device build was run as part of this CR (per instruction) — Saiful reviews on
  TestFlight per the usual cadence.

## Status

done
