# 02 — Pattern research: how good apps hide complexity

Patterns below are selected for one job: **keep a complex product simple at the
surface without amputating depth.** Each entry: what it is, who proves it, why
it fits AMI Trade.

## P1 — Progressive disclosure (the master pattern)

Coined from Jakob Nielsen's work (Nielsen Norman Group): present only the
essentials, reveal advanced capability on request. Reduces initial cognitive
load and error rates in complex systems. Common forms: accordions, "advanced"
sections, staged onboarding, detail-behind-summary.

- Fit: this is the *spine* of both recommended concepts. AMI Trade already has
  in-app precedent (CR106 board→transcript toggle, CR120 "SHOW ALL").
- Caveat from practitioners: disclosure is not a cure-all — if the information
  architecture underneath is wrong, hiding it behind taps just moves the mess.
  The concepts below fix the IA first (briefing/feed as the top level), then
  disclose.
- Sources: [UXPin — What Is Progressive Disclosure](https://www.uxpin.com/studio/blog/what-is-progressive-disclosure/) · [Octet Design](https://octet.design/progressive-disclosure/) · [Versions — The Art of Revealing Just Enough](https://versions.com/interaction/progressive-disclosure-the-art-of-revealing-just-enough/)

## P2 — One-thing-first fintech minimalism (Robinhood lesson)

Robinhood's redesign is the canonical case of taking an intimidating domain
(brokerage) and leading with one number and one action; their simplification
work is credited with a ~20% lift in downloads and higher new-user engagement.
Bold typography, high contrast, *very few choices per screen*.

- Fit: the "Portfolio pulse" strip and single primary CTA in both concepts come
  straight from this. Hick's Law: every additional choice on the home screen
  taxes the decision the user actually came to make.
- Sources: [Webstacks — Fintech redesigns](https://www.webstacks.com/blog/fintech-website-redesign) · [Phenomenon — Simplifying complex financial flows](https://phenomenonstudio.com/article/fintech-product-design-turning-complex-financial-flows-into-simple-experiences/)

## P3 — Guided path over feature grid (Duolingo lesson — with a warning)

Duolingo replaced its skill-tree home with a single guided path: one next
thing, always. Massive simplification of "what do I do now."

- Fit: lessons today are a 13-hex honeycomb — pretty, but a choice grid. A
  "one lesson keeps your streak" card is the path pattern applied to AMI.
- **Warning**: Duolingo's 2022 path redesign also drew real backlash (users
  lost a sense of map/progress and control). Lesson for AMI: *simplify the
  default view, but always leave the map reachable* — which is exactly the
  "desk drawer / team screen" escape hatch in both concepts.
- Sources: [Duolingo blog — new home screen](https://blog.duolingo.com/new-duolingo-home-screen-design/) · [UX Collective — the backlash](https://uxdesign.cc/down-the-wrong-path-the-disaster-of-the-latest-duolingo-ui-update-a4cdd1e6ea1c)

## P4 — Control surfaces, not chat-first, for agentic products

2025–26 agent-UX research converges on: pure chat interfaces fail for
multi-agent products because users can't see state, can't audit, can't undo.
What works: **summary surfaces with receipts** — verdict cards, "who agreed",
logs, and explicit approve/dismiss actions.

- Fit: kills the naive "just make the Concierge a chatbot" redesign (see
  Concept D, rejected). The recommended concepts put *structured verdict
  surfaces* (not chat bubbles) at the center, with the full debate as the
  receipt.
- Source: [HatchWorks — Agent UX patterns](https://hatchworks.com/blog/ai-agents/agent-ux-patterns/)

## P5 — Familiar navigation conventions (Jakob's Law)

Users spend most of their time in *other* apps; they bring expectations. A
bottom nav with 3–5 plain-word destinations, cards that tap to detail,
swipe-back — no relearning.

- Fit: both concepts keep a standard bottom nav (and B actually *reduces* it
  from 5 to 4). Nothing in the mockups requires a coach-mark tour to operate.
- Source: [Laws of UX](https://www.looppanel.com/blog/laws-of-ux)

## P6 — Mascot/single-character front door

Duolingo's Duo shows a single character can carry emotional connection and
absorb complexity that would otherwise need UI chrome. AMI Trade already has
this character: the **Concierge** — currently a section on the Floor, in the
redesigns promoted to the voice of the home screen.

- Fit: the Concierge is the *human-scale* interface to the 12-agent machine.
  "Your team flagged X" from one trusted voice beats 12 hexes staring at you.

## Synthesis — the layering model both concepts share

```
L0  BRIEF      One voice, one headline, one action.        ← default home
L1  VERDICT    Structured summary: call, conviction,       ← tap the action
               9-of-12 consensus, top dissent.
L2  DEBATE     Full transcript, per-agent views,           ← "read full debate"
               1-on-1 / brief an agent.
L3  MACHINERY  Overlays, safety floor, version history.    ← settings / sheets
```

Every layer is one tap from the layer above, and L0 never shows L2/L3
vocabulary. The 12 agents live at L1 (as a consensus strip + named dissent)
and L2 (as themselves) — never at L0.
