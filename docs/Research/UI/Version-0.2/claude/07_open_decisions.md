# 07 — Open decisions (Saiful)

Five calls only you can make. None block reading the research; #2 and #4 block a build.

1. **Tab-0 name.** If the landing is a Concierge card rather than the agent floor, does the
   tab stay FLOOR (brand continuity, slight misnomer) or become HOME / AMI? Interacts with
   CR133's label widths (its prototype measured 97.0pt cells — either fits).
   *Default if silent: keep FLOOR.*

2. **Voice of the home card.** Concierge (pink, D-014-sanctioned, product-help role — the
   frames as mocked) or CIO (purple, post-CR160, "your firm reporting")? A CIO voice reads
   more like a trading firm and less like an assistant — but D-015 forbids trading agents
   doing product help, so a CIO-voiced card must stay strictly in-role (status only, no
   navigation help), which complicates the ask affordance.
   *Recommendation: Concierge.*

3. **Room narrative default.** Concept E for everyone with WATCH THE FLOOR persisted
   (CR106's exact shape), or narrative for the first N runs only, then remember whatever the
   user last chose? First-N adds a counter and a second default policy for marginal gain.
   *Recommendation: default for everyone, persisted toggle.*

4. **CR159 re-scope.** CR159 was filed as the Floor itself; the recommendation demotes it to
   the "Your Firm" screen one tap down (flow A2). Same widgets, same traps, different
   mount point. Needs your explicit OK since it changes a filed CR's intent.
   *Recommendation: re-scope; the desk bands are better as an answer than a greeting.*

5. **Status-line composition.** Client-composed from existing state (free, offline-capable,
   the frames as mocked) vs a daily LLM digest (concept B's cost: new backend surface,
   per-user spend under CR057, stale on closed-market days).
   *Recommendation: client-composed now; a digest can upgrade the same card later without
   layout change.*

One process note, not a decision: user feedback like "the UI is too much" currently has no
capture path (CR043's loop is open at both ends). If a home CR ships from this research, its
acceptance should include a way to hear the same users again.
