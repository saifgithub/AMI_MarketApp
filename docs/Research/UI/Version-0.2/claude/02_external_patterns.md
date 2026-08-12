# 02 — External patterns

What the field knows about hiding complexity behind a simple surface. Every quote below was
verified against a live fetch of the cited page (2026-08-12); full URL list with
primary/secondary labels in `sources.md`. One source that could not be verified is flagged.

## 2.1 Progressive disclosure — the canonical answer

Nielsen Norman Group's formulation (Nielsen, 2006) is precisely the brief Saiful gave:

> *"Initially, show users only a few of the most important options. Offer a larger set of
> specialized options upon request."*

> *"Progressive disclosure defers advanced or rarely used features to a secondary screen,
> making applications easier to learn and less error-prone."*

The line that convicts the shipped Floor:

> *"In a system designed with progressive disclosure, the very fact that something appears
> on the initial display tells users that it's important."*

Twelve simultaneous agent hexes tell a day-one user that all twelve are equally important
right now — which is exactly the "12 staff waiting" reading. The design intent ("a room with
people in it") and the disclosure principle collide head-on at the landing surface. They do
not collide one tap deeper.

## 2.2 Cognitive load, decision time, choice overload

- **Cognitive load as budget** (NN/g, Whitenton 2013): *"The cognitive load imposed by a
  user interface is the amount of mental resources that is required to operate the system"*;
  performance degrades when incoming information exceeds capacity. Thirteen colour-coded
  identities + 23 tap targets is the Floor's opening bid against that budget.
- **Hick's law** (Hick & Hyman 1952, via lawsofux.com): *"The time it takes to make a
  decision increases with the number and complexity of choices."* The site's own takeaways:
  minimize choices when response time matters; *"avoid overwhelming users by highlighting
  recommended options"* — i.e. one primary CTA, not twelve peers.
- **Choice overload** (Iyengar & Lepper 2000, *JPSP* 79(6)): buyers engaged more and bought
  more *"when offered a limited array of 6 choices rather than a more extensive array of 24
  or 30."* Twelve always-on seats sits in the regime the paper tested as demotivating.

## 2.3 Agentic-system UX, 2025–2026 — summarize first, drill down on demand

The freshest research converges on the same shape:

- **NN/g on AI agents** (Liu & Rosala, May 2026): *"For AI agents to gain traction, users
  must be able to understand, guide, and trust them — capability alone is not enough."*
  Autonomy needs transparency — but transparency as *available*, not *ambient*.
- **NN/g on chat answers** (Rosala, Kenderova & Kohler, Apr 2026): *"Users turn to
  site-specific chatbots for quick answers, not a conversation"*; *"a longer answer was not
  a better answer."* Their participants' ideal: bullet points first, detail on request —
  the truncated-pyramid rule. This is CR106's Verdict Board, independently derived.
- **Anthropic's multi-agent research system** (2025): the reference architecture for AMI's
  situation — *"a lead agent coordinates the process while delegating to specialized
  subagents that operate in parallel,"* with subagents *"condensing the most important
  tokens for the lead research agent."* The user-facing surface is the orchestrator's
  synthesis. Nobody watches twelve raw streams.
- **Luke Wroblewski, agent management patterns** (2025): names the problem — *"How can
  people start, steer, and stop multiple agents (and subagents) and stay on top of their
  results?"* — and catalogs the answers (dashboard, inbox, task list), all summary surfaces
  with layered detail: *"provide high level (month) and detailed (day) views."*
- **Working-state pattern** (LukeW, Nov 2025): live process (traces, tool calls) shows
  while running, then *"the thinking steps … collapse into a summary."* Concept E is this
  pattern with AMI's desks as the stages.
- **Google Gemini Deep Research** (2024): the mainstream precedent for staged progress —
  *"it creates a multi-step research plan for you to either revise or approve,"* runs long
  work in the background, returns *"a comprehensive report of the key findings."* Hours of
  machinery, one narrative. (Perplexity's equivalent pages returned HTTP 403 and are
  **not cited** — see `sources.md`.)

## 2.4 One assistant fronting a complex machine — commercial precedents

- **Cleo** (TechCrunch 2018): one conversational persona fronts multi-account budgeting
  machinery; founder's thesis — *"you don't need to be a bank to become the primary way
  users interface with their finances."*
- **Intercom Fin** (fin.ai, fetched 2026): sold as *"a single customer facing Agent"* while
  a separate orchestration layer works *"behind the scenes."* A live commercial product
  whose entire pitch is: many agents inside, one face outside.
- **Robinhood** (company design story, 2021): *"We're focused on design that's friendly,
  that's inviting, that doesn't intimidate you, that isn't condescending."* The
  minimal-decision-screen ethos that won a 2015 Apple Design Award — complexity never
  pushed onto the user. First-party source; vendor self-description, weighted accordingly.

AMI already owns the asset these precedents argue for: **the Concierge is the 13th agent,
always free, with a sanctioned monopoly on the product-help role and the pink signature
(D-014/D-015)**. The pattern the field converged on is sitting in the app, one level below
where it should be.

## 2.5 What the external evidence does NOT license

- It does not license *deleting* the team — D-012 keeps twelve agents, and the CEO metaphor
  (D-003/D-013) is the product's identity. The evidence is about *when* the team appears,
  not *whether*.
- It does not license hiding the Brief-Your-Agent safety floor — D-024 mandates the locked
  block stay visible ("honest > paternalistic"), and nothing above conflicts: disclosure
  hides *depth*, never *disclosures*.
- It does not settle Simple-vs-Full modes — NN/g's progressive-disclosure article itself
  treats dual modes as a weaker cousin of a better default. Concept F documents this.
