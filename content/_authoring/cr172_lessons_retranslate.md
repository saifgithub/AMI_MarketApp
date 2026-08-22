# Lessons 316–322 — re-translation needed (CR172 criterion 10 → i18n lane)

CR172 acceptance criterion 10:

> *All AR/MS retranslation flagged per-`id` for lessons 316–322 and the new ARB strings.*

Options are now **simulated** in AMI Trade — the Room proposes a costed structure and the
ticket opens it — behind `Compliance.derivatives_allowed`, which is **False by default**. Three
EN lessons stated flatly that the product has no options trading. That was true when they were
written and is not true now, and it is the kind of claim a user checks against the app in front
of them.

The amendment does **not** simply flip the claim. It states the gate, because for a default user
nothing has changed: AMI will not propose or open a structure until derivatives are turned on in
the mandate. A lesson that said "you can trade options here" would be wrong for almost everyone
reading it.

Keyed by `id`. See [[feedback_content_change_flags_translation]].

| id | file | locales stale | why |
|---|---|---|---|
| `319_covered_call_and_protective_put` | `319_covered_call_and_protective_put.{ar,ms}.mdx` | ar, ms | "Try it" — *"There's no options trading in AMI Trade — this is a thought exercise"* → both structures are simulated, gated on `derivatives_allowed` being turned on, and the default-off state is named as deliberate |
| `320_implied_vs_realized_volatility` | `320_implied_vs_realized_volatility.{ar,ms}.mdx` | ar, ms | "Try it" — the *"since AMI Trade has no options trading"* clause replaced. The not-a-signal warning is kept and strengthened on its own terms (a rich option is not automatically one worth selling), rather than resting on a product limitation that no longer holds |
| `322_why_retail_options_lose_capstone` | `322_why_retail_options_lose_capstone.{ar,ms}.mdx` | ar, ms | "Try it" — *"Remember: AMI Trade has no options trading"* → the exercise now continues into the simulator for a user with derivatives on, which is the upgrade the CR predicted for this capstone: the bar the lesson describes is the same bar, priced, on a card AMI costed |

**NOT stale:** `316_calls_and_puts`, `317_payoff_diagrams_intrinsic_time_value`,
`318_the_greeks_delta_theta_vega`, `321_futures_and_forwards`. Swept for the same claim and they
never carried it — 321's only near-match is a quiz explanation contrasting a long call's
structural floor with a futures obligation, which is instrument arithmetic and is unaffected.
Flagging them anyway would cost three translators' time to change nothing.

**New ARB strings:** none yet. The mobile ticket (`option_proposal_ticket.dart`) ships its own
strings and is not wired to a Room verdict, so no new user-visible option copy has reached the
Flutter i18n surface. When the wiring lands, its ARB keys are flagged here.

**Guard note.** `content/_authoring/locale_staleness_check.py` mechanism 1 (`source_sha`) would
have caught these automatically had the translation pipeline stamped it; it does not yet, so the
siblings report UNSTAMPED and fall to mechanism 2 (anchor divergence). Anchor divergence will
**not** catch these three: the edits change prose, not tickers, numbers, URLs or component ids,
so the anchor multiset is unchanged. That is precisely DEF105's shape — *"these parse fine and
pass the serving-time integrity gate"* — and it is why this file is hand-written rather than
generated. The standing fix is CR060 Phase 6's per-`id` `source_sha` stamp.
