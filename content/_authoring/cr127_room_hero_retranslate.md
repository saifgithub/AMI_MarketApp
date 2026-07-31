# Room hero card — AR/MS review needed (CR127 → i18n lane)

Mobile ARB strings changed or added under CR127 whose **user-facing meaning changed**.
Keyed by ARB key. See [[feedback_content_change_flags_translation]].

**These are not machine-translated and not blocking.** Each AR/MS value below was composed
from a rendering already attested elsewhere in the same ARB, rather than invented — but a
native pass should still confirm grammar and register, because two of the three are verb
phrases where the subject changed and Arabic verb agreement moves with it.

| key | file | locales | EN before → after | AR/MS basis |
|---|---|---|---|---|
| `roomHeroPmCard` | `app_{en,ar,ms}.arb` | ar, ms | *(new key)* → `PORTFOLIO MANAGER` | AR `مدير المحفظة` — the rendering already used for "Portfolio Manager" in `roomOverrideHeading`, `settingsMaxDrawdownExplain`, `tradeTicketFooterNote` and 2 others. MS `PENGURUS PORTFOLIO` — composed from `Pengurus` (attested for "Manager" in `upgradePlanFloorManager`) + `Portfolio` (used untranslated throughout the MS file). **MS is the one to check**: `roomOverrideHeading` uses the bare abbreviation `PM` instead, so the file is currently inconsistent about which form to use for this agent. |
| `roomHeroApprove` | `app_{en,ar,ms}.arb` | ar, ms | `THE ROOM APPROVED` → `THE PM APPROVED` | Subject swapped from "the room" to the PM. AR `وافقت الغرفة` → `وافق مدير المحفظة` (verb drops the feminine `ت` — `الغرفة` is feminine, `مدير` is masculine). MS `BILIK MELULUSKAN` → `PM MELULUSKAN`. |
| `roomHeroPass` | `app_{en,ar,ms}.arb` | ar, ms | `THE ROOM PASSED` → `THE PM PASSED` | Same subject swap. AR `تجاوزت الغرفة` → `تجاوز مدير المحفظة`. MS `BILIK BERLALU` → `PM BERLALU`. **Worth a second look in both**: this is PASS as in "declined to take a position", not "passed a test" — the EN carries that from context, and `BERLALU` (elapsed/went by) may not. |

**Removed, no action:** `roomCombPmDecides` (`THE PM DECIDES — THIS IS NOT A VOTE` /
`مدير المحفظة هو من يقرر — هذا ليس تصويتاً` / `PM YANG MEMUTUSKAN — INI BUKAN UNDIAN`) is
deleted from all three locales — the hero card now carries the disclosure structurally.
