# R06 — Eliza / elizaOS

**Repo:** github.com/elizaOS/eliza · surveyed 2026-09-20 as part of an 8-repo stack survey (see
`../../02_oss_stack_survey.md`).

## What it is

A general-purpose open-source AI agent framework (TypeScript) — chat, memory, plugins,
wallet/blockchain operations — for building autonomous agents across many domains. It is not
trading-specific, and trading logic would be entirely user- or plugin-supplied.

## Our verdict

**NO TESTABLE CLAIM (framework)** — but flag the adjacent token story separately, below.

## Why this verdict, not a test

The framework itself makes no assertion about trading outcomes; it is agent scaffolding, the same
category as R01 (AI Hedge Fund), just not even trading-specific. Nothing to pre-register.

## Separate flag: the ai16z / ELIZAOS token

This is **not a strategy-performance claim** and does not change the verdict above, but it is
worth recording because it is the kind of story this channel exists to warn about: the `ai16z`
community's associated `ELIZAOS` token was marketed as an "autonomous AI trading agent" and is now
the subject of a federal class-action lawsuit alleging it was in fact manually operated and
misrepresented as self-investing; the token is reported down more than 99.9% from its roughly
$2.6B peak market cap, with a heavily insider-weighted allocation and large early sell-offs cited
in the complaint. This is a **token/marketing fraud allegation about a launch**, not a demonstrated
failure of the open-source framework's code or of any bundled strategy — the framework and the
token are related by branding, not by the token's claims being derived from the framework's code.

## Revisit if

- The class action resolves with findings of fact — those findings, not our own test, would be the
  citable evidence for a future "how to spot a wrapped fraud" episode (B07's "why you can't check
  this" angle already covers the same ground for undisclosed-logic bots).
- Do not pre-register a "test" of the token claim — it is not mechanised, there is no recipe, and
  the claim is about operator conduct, not a trading rule.

## Track record note (context only, not a verdict input)

Large, actively developed framework, high profile due to the token controversy. Framework code
itself carries no known independent trading-performance evaluation.
