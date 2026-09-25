# DEF430 — draft wording: Terms v4.2 and Privacy v2.1 (Alpaca)

Saiful's ruling, 2026-09-25: *"I draft, you approve."* Nothing here is published until he approves.
Prepared by the Architect. The legal review (A22) checks the published result later.

## What the app actually does (checked in code, 2026-09-25)

| Fact | Where |
|---|---|
| Alpaca API keys are kept in the device's secure storage (Keychain / Keystore) and never sent to AMI. The server keeps only the date an account was linked. | `mobile/lib/services/alpaca/alpaca_credential_store.dart`; `backend/app/db/models.py` (`alpaca_linked_at`) |
| Orders go from the device directly to Alpaca, and only to a paper-trading host. The app refuses to send an order or a cancel to a live account. | `mobile/lib/services/alpaca/alpaca_client.dart` (paper-host check before every POST and DELETE) |
| A live account can be linked read-only: the host is user-overridable. | `alpaca_client.dart:7` |
| For **any** linked account, paper or live, the device sends the account summary with every Room convene and every 1-on-1 message. The summary is cash, buying power, total value and, per position, symbol, quantity, market value and unrealised P/L. It is written into the agents' prompts. | `mobile/lib/state/alpaca_providers.dart` (`AlpacaSnapshotCache`, no paper check); `backend/app/schemas/alpaca.py` |
| An order preview for an Alpaca destination (paper only) sends the account's equity, cash and positions for the mandate check. It is not stored. | DEF419; `test_account_context_preview_never_persists` |
| The snapshot is not saved as its own record. Agent replies and Room analyses that refer to it are stored like any other agent conversation. | Privacy clauses 3 and 9 |
| Prompts may be routed to a contracted third-party AI provider. The snapshot is part of the prompt, so it travels with it. | Privacy clauses 7 and 8 |

## Terms of Service v4.2: clause 1, second paragraph

**Now (v4.1):**
> You cannot buy or sell real assets through AMI Trade. The "Trade" actions in the app place orders against an internal simulation only; no order is ever routed to a brokerage, exchange, or market maker.

**Proposed:**
> You cannot buy or sell real assets through AMI Trade. The "Trade" actions in the app place orders against an internal simulation. If you link an Alpaca **paper-trading** account, you can also choose to send an order to that paper account; paper accounts trade simulated money, not real money. AMI Trade never sends an order to a live (real-money) brokerage account: if you link one, the app only reads it and refuses to place or cancel orders in it. Your relationship with Alpaca, including its own terms and privacy policy, is between you and Alpaca.

Version history line: *v4.2 (date): clause 1 now describes optional Alpaca paper-trading links; live accounts are read-only.*
Materiality: under clause 13, a material change is one that expands restrictions, changes pricing or narrows the user's rights. This change does none of those, so no 14-day notice is needed.

## Privacy Policy v2.1: add to clause 3 ("What we collect when you use the AMI agents")

**New paragraph:**
> **If you link an Alpaca brokerage account.** Your Alpaca API keys stay in your device's secure storage and are never sent to us; we record only that, and when, you linked an account. When you convene the Room or message an agent, the app reads your linked account's current summary (cash, buying power, total value, and each position's symbol, quantity, market value and unrealised profit or loss) and sends it to us with that request, so the agents can take your real holdings into account. When you preview an order to your Alpaca paper account, the app sends the same summary so the mandate check can size the order against it. We do not store the summary as its own record; it is used for that request, and any agent reply or Room analysis that refers to it is kept like your other agent conversations (clause 9). Because it is part of the request to the AMI agents, clauses 7 and 8 apply to it. This happens for any account you link, including a live account linked read-only. Unlink the account in the app to stop it.

Version history line: *v2.1 (date): clause 3 now describes the account summary sent when you link an Alpaca account.*

## The notice question (Saiful's call)

Clause 16 makes "meaningfully expand what data we collect" a **material** change, with 14 days' notice by in-app banner or email. The app has been doing this since CR202 shipped (about 2026-09-22), so v2.1 corrects the policy to match current practice rather than announcing a new one. The recommended handling, which covers both the correction and the notice:

1. **Publish v2.1 now** so the policy is accurate as soon as possible.
2. **Add a disclosure on the Alpaca link screen**, shown before a user links, stating the paragraph above in short form. That is consent at the point of collection, since linking is opt-in. It is a small mobile change and would need its own ID.
3. **Show an in-app banner** announcing the v2.1 change, which satisfies clause 16 for anyone who linked before step 2 shipped.
4. **Legal (A22)** reviews the result.

Alternative (Saiful's option at the time of the ruling): turn Alpaca linking off for external testers until the above ships.

## Also worth deciding

The snapshot is sent for a **live** account too. If Saiful prefers that live holdings never leave the device, the change is one line in `AlpacaSnapshotCache` (paper-host check before building the snapshot), and the Privacy text above shrinks to paper accounts only. That is a product call: live holdings give the agents real context, but they are real financial data.
