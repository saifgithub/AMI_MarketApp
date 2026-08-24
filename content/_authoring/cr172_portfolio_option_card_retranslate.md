# CR172 §12 — portfolio option card: AR/MS retranslation required

**Filed:** 2026-08-24 (AT:R74) · **CR:** CR172 · `retranslate:[ar,ms]`

15 new EN keys in `mobile/lib/l10n/app_en.arb`. `app_ar.arb` and `app_ms.arb`
carry the **English text as a seed**, with a matching `@@x-ami-seeds` hash
(`sha256(en_value)[:12]`). A key counts as untranslated only while its value
still hashes to the recorded hash — a real translation is simply **absent** from
that map, so the seeding is self-healing and no cleanup step is owed.

## Keys

| Key | EN |
|---|---|
| `portfolioOptionsHeading` | OPTION POSITIONS |
| `optionSideLong` | LONG |
| `optionSideShort` | SHORT |
| `optionRightCall` | CALL |
| `optionRightPut` | PUT |
| `optionLegLine` | `{side} {contracts} {right} ${strike}` |
| `optionLegLineDated` | `{side} {contracts} {right} ${strike} · {expiry}` |
| `optionDaysToExpiry` | `{days} days to expiry` |
| `optionExpiresToday` | EXPIRES TODAY |
| `optionExpiresTomorrow` | EXPIRES TOMORROW |
| `optionExpiredSettling` | EXPIRED — AWAITING SETTLEMENT |
| `optionPaidAtOpen` | `Paid ${amount} at open` |
| `optionCollectedAtOpen` | `Collected ${amount} at open` |
| `optionCollateralHeld` | `Collateral held: ${amount}` |
| `optionMarkUnavailable` | No live mark yet — this shows what the structure cost, not what it is worth today. |

## Five that need a translator's judgement, not a dictionary

These are called out because a literal rendering changes what the user
believes, and four of the five are about money the user either owes or cannot
spend.

1. **`optionRightCall` / `optionRightPut`** — derivatives terms of art. `CALL`
   is not a telephone call and `PUT` is not the verb. Most markets keep the
   English word or use an established local term; inventing a descriptive
   phrase here would make the leg line unreadable to anyone who has seen a
   chain before.

2. **`optionSideLong` / `optionSideShort`** — the finance senses (a position
   owned vs a position owed), never length or size. `optionSideShort` should
   match whatever `shortPositionBadge` was already translated to, because both
   appear on the same screen and a user seeing two different words for one
   concept will reasonably assume they are two concepts.

3. **`optionCollectedAtOpen`** — must **not** read as a profit. The user
   received cash up front against an obligation that is still outstanding.
   "Earned", "gained" or "made" would all be wrong in a way that flatters the
   position.

4. **`optionCollateralHeld`** — must not read as a charge, a fee, or a loss.
   This cash is set aside and comes back when the structure closes. It is
   unavailable, not gone.

5. **`optionExpiredSettling`** — must not read as *"this position is closed"*
   and must not read as an error or a glitch. The position is genuinely still
   on the book; the sentence exists so the user is told why, rather than
   discovering a stale row and distrusting the whole screen. This is a
   degrade-loudly state (CR040), and its whole job is to prompt a question.

## One deliberate absence

There is **no P&L string**, and none should be added. The option marks feed
(CR172 §11) is unbuilt, so no unrealised figure is computable. `optionMarkUnavailable`
is what stands in its place: it says the card shows **cost**, not **worth**. A
`$0.00` in a P&L slot reads as *flat*, which is a measurement, when the truth is
*not measured* (DEF059) — and on a position that decays by construction, that
particular false reading would be the most expensive one available.
