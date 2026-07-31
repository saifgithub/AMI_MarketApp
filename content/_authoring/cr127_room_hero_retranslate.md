# Room board — AR/MS review needed (CR127 → i18n lane)

One new mobile ARB key added under CR127. Keyed by ARB key.
See [[feedback_content_change_flags_translation]].

**Not machine-translated and not blocking.** The AR/MS values were composed from a
rendering already attested elsewhere in the same ARB rather than invented — but a native
pass should still confirm register.

| key | file | locales | EN | AR/MS basis |
|---|---|---|---|---|
| `roomPmCardHeading` | `app_{en,ar,ms}.arb` | ar, ms | `PORTFOLIO MANAGER` | AR `مدير المحفظة` — the rendering already used for "Portfolio Manager" in `roomOverrideHeading`, `settingsMaxDrawdownExplain`, `tradeTicketFooterNote` and 2 others. MS `PENGURUS PORTFOLIO` — composed from `Pengurus` (attested for "Manager" in `upgradePlanFloorManager`) + `Portfolio` (used untranslated throughout the MS file). **MS is the one to check**: `roomOverrideHeading` uses the bare abbreviation `PM` instead, so the file is currently inconsistent about which form to use for this agent. |

**Removed, no action:** `roomCombPmDecides` (`THE PM DECIDES — THIS IS NOT A VOTE` /
`مدير المحفظة هو من يقرر — هذا ليس تصويتاً` / `PM YANG MEMUTUSKAN — INI BUKAN UNDIAN`) is
deleted from all three locales — the PM's own titled card carries the disclosure now.

**Unchanged:** `roomHeroApprove` / `roomHeroPass` keep `THE ROOM APPROVED` / `THE ROOM
PASSED` in all three locales. An earlier draft of this CR re-attributed them to the PM;
Saiful reverted that — the hero reports the run's outcome, and the PM speaks in its own
card lower down.
