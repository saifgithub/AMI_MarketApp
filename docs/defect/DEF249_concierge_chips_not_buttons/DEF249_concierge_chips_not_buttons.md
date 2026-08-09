# DEF249 — two accessibility defects in the semantics layer, both invisible on Android

**Filed:** 2026-08-10 · **Source:** uat · **Category:** ui_glitch · **Status:** fixed · **Session:** AT:R66

Both were found by the **first-ever iOS UAT run** (CR162), and neither could have been
found on Android or by a widget test. Two symptoms, one theme: the app's `Semantics`
usage is wrong in ways only the *platform* accessibility tree reveals.

## Finding 2 — every bottom-nav destination is announced twice

`hex_bottom_nav.dart`'s `_Cell` wrapped its content in
`Semantics(button: true, selected: active, label: item.label, …)` while the child `Text`
already rendered `item.label`. Flutter concatenates the two. Measured on the live
Simulator:

```xml
<XCUIElementTypeButton name="ami.nav.floor" label="FLOOR&#10;FLOOR"
                       traits="Selected, Button" x="0" y="747" …/>
```

A VoiceOver user hears "FLOOR FLOOR" on every one of the five destinations. It also broke
the harness's exact-text locator and therefore the onboarding walk's "have we landed on
Floor yet?" probe — which is how it surfaced.

**This predates CR162**; the `label:` line is original to CR016. Android never showed it,
because there the child `Text` keeps its own separate semantics node and `text("FLOOR")`
matched regardless.

**Fix:** drop the redundant `label:` — the child `Text` supplies it. Guarded by
`mobile/test/qa/semantics_ids_test.dart::a destination is announced once, not twice`,
which asserts on the node's label. A tap test passes on the broken build, and so does
every Android run; only a label assertion catches this.

## Finding 1 — Concierge answer chips are not exposed as buttons

`mobile/lib/widgets/chat/chip_row.dart`'s `_Chip` is a bare `GestureDetector` wrapping a
`ClipPath`/`Container`/`Text`. It carries no `Semantics(button: true)`, so the platform
accessibility tree reports it as **static text**.

Measured on the live iOS Simulator build, first screen of the Concierge interview
(page source captured 2026-08-10, `AMI_QA_SEMANTICS=1` build):

```xml
<XCUIElementTypeStaticText value="Save for retirement"  … traits="StaticText"/>
<XCUIElementTypeStaticText value="Build long-term wealth" … traits="StaticText"/>
<XCUIElementTypeStaticText value="Generate income now" … traits="StaticText"/>
```

The only element on that screen with `traits="Button"` is the 48×48 send arrow beside the
text field.

## Why it matters

**For users:** a VoiceOver user reaches the first question of onboarding, hears four
phrases announced as plain text, and gets no signal that any of them is actionable. The
typed-answer field is reachable, so the interview is completable — but the chips, which are
the intended fast path, are effectively invisible as controls. This is the *first screen of
the app*, before the user has any other context to fall back on.

**For testing:** this is what blocked the first iOS UAT run. Android's accessibility bridge
marks any tappable node `clickable` regardless of semantics flags, which is why the Appium
harness has walked this interview happily since CR080. iOS has no `clickable` concept — a
node is a button only if Flutter says so — so `interactive_elements()` found exactly one
candidate (the send arrow), tapped it repeatedly with an empty field, and timed out after
120s.

That asymmetry is the useful part of this finding: **Android testing could never have
surfaced it**, and neither could a widget test, because both see Flutter's own tree rather
than the platform's.

## Scope

Not just the chips. Across `mobile/lib`: **24 `GestureDetector(` occurrences in 20 files**,
of which only **7 files** mention `Semantics(` at all. (`InkWell`, used 33 times, does get
button semantics for free — so the exposure is specifically the `GestureDetector` sites.)

This defect covers the Concierge chips, which are confirmed-by-measurement and block
onboarding. The wider sweep is **not** claimed as broken here — some of those
`GestureDetector`s wrap genuinely non-interactive affordances, and each needs looking at
rather than a blanket edit. The iOS harness will now surface them systematically as it
gains screen coverage, which is the right way to find the real ones.

## Fix

Wrap `_Chip` in `Semantics(button: true)` — **without** a `label:`, which would hit
Finding 2's duplication (the first attempt did exactly that, and the new widget test
caught it before it shipped). One widget, and it fixes the real accessibility bug rather
than working around it in the harness — per this project's preference for structural
fixes over test-side compensation.

Confirmed on the live Simulator after the fix: `XCUIElementTypeButton` count went 2 → 10,
`XCUIElementTypeStaticText` 18 → 10, and each chip now reads
`<XCUIElementTypeButton name="Save for retirement" label="Save for retirement" …>`.
Guarded by `mobile/test/widgets/chip_row_test.dart`.

## Related

- CR162 (the iOS harness that found it), CR080 (the Android harness that could not)
- flutter#25485 — the semantics-tree gating that made iOS automation impossible until CR162
