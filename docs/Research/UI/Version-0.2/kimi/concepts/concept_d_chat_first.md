# Concept D — "Chat-first Concierge" (documented, not recommended)

**One-liner:** replace the home screen with a single chat thread with the
Concierge; everything the app does is invoked conversationally.

## Principle

The most literal reading of "hide all the complexity": no tabs, no grids, no
cards — just "Good morning. Want today's call?" The Concierge becomes the
entire interface; the 12 agents are pure backstage.

## Why it's attractive

- Nothing to learn. Zero visible chrome. Onboarding already works this way
  (the chat interview), so there's precedent in-app.
- LLM-native: the Concierge engine exists.

## Why it's rejected

1. **Chat-first fails for agentic products.** Current agent-UX research is
   blunt: users of multi-agent systems need *control surfaces* — state,
   receipts, approvals, undo — not a scrollback ([HatchWorks](https://hatchworks.com/blog/ai-agents/agent-ux-patterns/)).
   A chat home gives no persistent answer to "where do I stand?"
2. **Discovery collapses.** Portfolio, journal, league, lessons become
   things you must *remember to ask for*. Features behind a prompt box get
   used by power users only.
3. **Auditability is the brand.** A simulation trading *education* app must
   show its work — verdict cards, consensus, dissent. Chat buries exactly the
   receipts that make the product trustworthy.
4. **Latency + cost on the critical path.** Every home open becomes an LLM
   call. The recommended concepts only need templated prose at L0.
5. **Typing is the highest-friction mobile input.** The complaint was "too
   much," but the fix shouldn't trade reading load for interaction friction.

## What to salvage

The Concierge's *voice* — which is why both recommended concepts make it the
narrator of a **structured** surface (briefing card / feed cards) instead of
a chat box. Chat stays where it's good: onboarding, 1-on-1, Brief.
