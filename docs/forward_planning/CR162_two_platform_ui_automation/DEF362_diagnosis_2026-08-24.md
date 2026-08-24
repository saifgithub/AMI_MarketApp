# DEF362 — why the iOS walk reports "did not reach Floor", and why a third blind re-run would say the same

**Written:** 2026-08-24 (AT:R74). **Method:** Saiful ruled *"Diagnose before re-running"* — two
blind re-runs had already been spent, and each cost ~9 minutes to produce the same uninformative
sentence. This is a code + evidence diagnosis. **No third run was spent to produce it.**

---

## The reported symptom, and why it is misleading

`pytest -m smoke` → 6/6 error, each `TimeoutError: onboarding did not reach Floor within 480.0s`.
That sentence names the app as the suspect. The evidence in DEF362's own row says otherwise:

> a screenshot taken while the walk was running shows the simulator sitting on the **iOS home
> screen** — the app under test was not in the foreground at all

So the walk spent its entire 480-second budget tapping a UI that was not ours, and then reported
that onboarding did not complete. That is the failure the walk **already has a guard for**, and the
guard's own comment describes this exact scenario from the Android side:

> *Measured: a run left AMI Trade and spent the full 300s tapping the Samsung dialer's keypad, then
> reported "onboarding did not reach Floor", which reads exactly like the app failing to start.*

The guard exists. It did not fire. **That** is the defect.

## Why the guard did not fire

`qa/appium/helpers/onboarding.py:136`:

```python
def _is_app_foreground(driver, app_id: str) -> bool:
    try:
        return driver.query_app_state(app_id) == _FOREGROUND
    except Exception:
        # Cannot tell. Assume we are still home rather than manufacture an
        # escape — a false escape would relaunch the app mid-interview and
        # throw away real progress.
        return True
```

**The detector fails open.** "Cannot tell" and "we are fine" return the same value, so the one
condition the guard exists to detect is indistinguishable from the guard working. The comment
argues the trade honestly — a false escape costs real interview progress — but the cost it weighs
is the cost of being *wrong in one direction only*. Being wrong in the other direction costs the
entire run **and** mislabels it as an app failure, which is what has now happened twice.

This is the house's own recurring class, stated in `CLAUDE.md`: *if this fires constantly and
silently, what does the user end up believing?* Here the operator ends up believing the app cannot
start. Two point fixes (DEF347, DEF348) were aimed at that belief.

**Corroborating detail — the diagnostic is Android-only too.** `_foreground_package` (line 146) is
`driver.current_package`, and its own docstring says *"Android-only, best effort"*. On iOS it
raises, so even a correctly-detected escape can only ever report *"an unidentified app"*. Both the
detection and its explanation are shaped for the platform that is not failing.

## What most likely put the app in the background

`POST /wda/keyboard/dismiss` returning **400 `invalid element state`**, in the same keyboard
handling DEF348 touched. `hide_keyboard_if_shown` (`gestures.py:154`) swallows every exception:

```python
try:
    if driver.is_keyboard_shown():
        driver.hide_keyboard()
except Exception:
    pass  # best-effort only
```

Appium's iOS `hide_keyboard` default strategy taps outside the keyboard region. A tap that lands
outside the app's own bounds is exactly how a simulator ends up at the home screen. **Stated as the
leading hypothesis, not as an established cause** — the row's discipline of not guessing is kept
here. What *is* established is that when it happens, nothing in the harness can see it or say so.

## Why this is not yet the third Dilemma instance

DEF362's row set the rule: a third *"the walk cannot complete"* becomes a Dilemma, because the
framing would then be the suspect. That threshold is about **the walk being unstabilisable one
hazard at a time**. This diagnosis does not add a third hazard to that list — it says the previous
two rounds were flying blind, because the instrument that should have named the hazard reports
"fine" when it cannot see. Fixing an instrument is not the same move as fixing another hazard.

**The honest framing for Saiful:** if the walk fails again *after* the detector can distinguish
"cannot tell" from "in the foreground", that failure is the third instance and it is a Dilemma —
and it will at least come with a real observation attached.

## The fix, and what must be proven

1. `_is_app_foreground` returns a **three-state** answer — foreground / not-foreground / unknown —
   and `unknown` is reported every time rather than silently coerced to foreground.
2. An `unknown` that persists is a failure with its own message, distinct from
   *"did not reach Floor"*. A walk that cannot see the app must never report on the app.
3. `_foreground_package` becomes platform-aware, so an iOS escape names something.
4. `hide_keyboard_if_shown` stops swallowing the iOS 400 silently — at minimum it is logged, since
   it is the leading candidate for the backgrounding.

**Guard:** the detector's three states are unit-testable against a fake driver with no simulator in
the loop, and must be — the current version's failure mode is precisely that it cannot be observed
from outside. Mutation-prove each: a detector that cannot fail its own test is what produced this.

## Filed as

**DEF366** — *the iOS walk's escape detector fails open, so a lost foreground reports as an app
failure*. DEF362 stays open and is now blocked on DEF366 rather than on a re-run.
