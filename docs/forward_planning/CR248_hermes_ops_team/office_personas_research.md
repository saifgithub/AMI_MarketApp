# Office personas research — small app-development office

Working doc (2026-10-04, AT:K6). Lens: a small application-development office with a
FEW HUMAN STAFF (e.g. 2–5 devs + founder). Which Hermes personas/profiles run the
office alongside the humans? Complements `launch_ai_team_design.md` (product-ops lens)
— this one is the office-operations lens. Feeds the "office assistant" product frame
in `consultancy_running_note.md`.

## Existing roster vs office needs

We already have (live on minihost): neteng, appsupport, customersupport (whatsapp +
email), angelia (Chief of Staff). Those cover product-ops. The office lens adds roles
around the humans who build software.

## Proposed office personas

| # | Persona | New or absorbed | What it does day-1 | Needs |
|---|---|---|---|---|
| 1 | **Delivery lead (PM)** | absorbed into angelia + kanban | board hygiene, standup summaries from commits/activity, deadline nags, weekly "where are we" to the founder | Hermes native kanban (video pick, not yet wired); git read access |
| 2 | **Code reviewer** | new profile | reviews PRs, posts review comments as drafts, runs/reads CI results, flags convention drift, weekly quality summary | repo access (git + GitHub/GitLab webhook or poll); read-only on main, never merges |
| 3 | **Release manager** | new profile | version bumps, changelog drafts, promotion runbooks (e.g. /promote-to-alpha steps), store-submission checklists (TestFlight/Play), release-notes drafts | ssh to build/promote hosts; Tier-1 actions (real store submits) stay human-approved |
| 4 | **Finance clerk** | new profile (cheap) | drafts invoices, tracks receivables in a sheet, expense summaries, month-end one-pager to founder | email + spreadsheet only — no terminal needed; safest persona in the office |
| 5 | **Sales/BD assistant** | new profile | lead list upkeep, follow-up reminders, proposal/quote drafts from templates, CRM-ish sheet | email + web research; outbound sends = draft-for-human (Tier 1) |
| 6 | **Research/analyst** | absorbed (skill, any profile) | "should we use X" evaluations, competitor scans, tech-stack research memos | web toolset; shares findings as docs |
| 7 | **Documentation writer** | absorbed (skill) | README/changelog/onboarding upkeep, API doc drafts from code | repo read access; PRs are drafts |
| 8 | HR/office admin | absorbed into angelia | onboarding/offboarding checklists, meeting scheduling, leave tracking | calendar/contacts via Google Workspace CLI (if adopted) — not a separate persona at this size |

## What the HUMANS keep

9. Tier 1 stays human per `you_do_i_do.md`: merges to main, store submissions,
   payments/invoices sent, legal, hiring/firing, production DB access. Personas
   draft-and-queue; humans approve. The SOUL pattern for every office persona:
   "draft for named-human approval; never execute Tier-1."
10. Architecture and product decisions — the delivery lead *surfaces* options;
    humans decide.

## Priority if built in order

11. Delivery lead (absorbed — cheapest; kanban + angelia SOUL extension, no new
    profile). 2. Finance clerk (cheapest new profile; immediate value for the
    consultancy office; zero dangerous toolsets). 3. Code reviewer (highest leverage
    on dev quality; needs webhook wiring). 4. Release manager (mostly runbook
    automation of what Kimi/Claude sessions already do by hand — strong
    office-assistant product story: "your release process as a persona"). 5.
    Sales/BD (only when the consultancy has prospects).

## Mapping to the video's builds (what's already demonstrated)

12. GitHub PR-review agent (course guide) → code reviewer persona. Kanban PM →
    delivery lead. Morning briefing → office ritual (pick pending). Agent email →
    done (finance/sales personas reuse the same adapter pattern — a second email
    address per persona is trivial now that the pattern is proven). Leads scraping →
    sales assistant (defer). Google Workspace CLI → documentation/HR absorb.

## Open questions for Saiful

13. Which two to build first — my recommendation: delivery lead + finance clerk
    (both cheap, both immediately useful, both safe).
14. For the office-assistant product: this roster IS the reference architecture for
    "small app-development office" — worth a page in the product doc when it exists.
15. Do code reviewer / release manager get the same whatsapp-group presence as the
    ops personas, or live behind angelia (humans ask her, she delegates)? Latter
    scales better; former is faster to use.
