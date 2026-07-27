# Lessons — re-translation needed (→ i18n / language manager)

EN lesson bodies edited after their AR/MS siblings were translated. The siblings now teach something the EN
no longer says (the DEF105 silent-divergence class). `locale_staleness_check.py` flags these automatically;
this manifest is the human-readable hand-off. See [[feedback_content_change_flags_translation]].

| lesson | locales stale | defect | why | safe to translate now? |
|---|---|---|---|---|
| 349_the_three_financial_ratio_screens | ar, ms | DEF118 | EN reframed so the halal flag no longer claims to compute the ratios live — it defers to a sourced AAOIFI index (CR069). Added two `<Lesson 355>` refs; changed intro / Example / Quiz-1 explanation / Try-it / Takeaway prose | **YES** — EN is final |

## Coordinate before translating the DEF105 cohort

The DEF105 cohort (`017, 047, 050, 051, 109, 204, 205`) was rewritten to *remove* phantom-Mandate-cap claims
(strip). **Saiful has since decided to BUILD those caps (CR101)** — so those EN lessons will likely be reverted
to teach the caps once the fields ship. **Do not re-translate the stripped versions yet** — they will change
again. Translate 349 now (it is independent of CR101); hold the DEF105 seven until CR101 lands and their EN is
re-settled.

**Guard:** `python3 content/_authoring/locale_staleness_check.py` lists every stale `.ar`/`.ms` sibling.
