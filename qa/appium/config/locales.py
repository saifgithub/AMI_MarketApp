"""Per-locale content strings for the multi-language UAT matrix (CR080 Phase 3).

Every string below is copied verbatim from mobile/lib/l10n/app_{locale}.arb as it
stood on 2026-07-25 (post CR083 translation delivery + CR087 AR lesson serving) —
never guessed or back-translated. Re-verify against the live ARBs whenever a
CR083/CR087-class change ships; a stale hardcoded string here would silently stop
testing the real app copy and every locale check would pass for the wrong reason.

Known real gaps found while extracting this table (not harness bugs — the app's
actual current state, flagged to Saiful separately, not fixed here):
  - `tabFloor` is untranslated in both AR and MS ("Floor" stays Latin-script/English
    in every locale) — could be a deliberate brand-term choice (matches
    `floorConciergeHeading` = "AMI CONCIERGE", also untranslated everywhere) or a
    missed key; not this harness's call.
  - `tabPortfolio` / `portfolioHeading` stay "Portfolio"/"PORTFOLIO" in MS only
    (AR translates both to "المحفظة").
  - `conveneHeading` mixes scripts: AR = "CONVENE الغرفة" (English word inside an
    Arabic sentence), MS = "CONVENE BILIK" (same pattern) — inconsistent with
    `conveneCta`/`floorConveneCta`, which get fully translated (AR) or fully
    untranslated (MS "CONVENE") for the *same* concept. Looks like a genuine
    translation-consistency defect, not an intentional brand term.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LocaleProfile:
    code: str  # matches Locale.languageCode in mobile/lib/i18n/locale_provider.dart
    switcher_native_name: str  # exact row text tapped in Settings -> Language
    rtl: bool
    tab_labels: dict[str, str] = field(default_factory=dict)  # base_page.TAB_LABELS key -> display text
    strings: dict[str, str] = field(default_factory=dict)  # semantic key -> display text


LOCALES: dict[str, LocaleProfile] = {
    "en": LocaleProfile(
        code="en",
        switcher_native_name="English",
        rtl=False,
        tab_labels={
            "Floor": "Floor",
            "Portfolio": "Portfolio",
            "Journal": "Journal",
            "Lessons": "Lessons",
            "Settings": "Settings",
        },
        strings={
            "floor_concierge_heading": "AMI CONCIERGE",
            "floor_convene_cta": "CONVENE THE ROOM",
            "convene_confirm": "CONVENE",
            "portfolio_heading": "PORTFOLIO",
            "portfolio_total_value": "TOTAL VALUE",
            "portfolio_cash": "CASH",
            "journal_heading": "DECISION JOURNAL",
            "journal_filter_all": "ALL",
            "lessons_heading": "LESSONS",
            "settings_heading": "SETTINGS",
            "settings_mandate": "MY MANDATE",
        },
    ),
    "ar": LocaleProfile(
        code="ar",
        switcher_native_name="العربية",
        rtl=True,
        tab_labels={
            "Floor": "Floor",
            "Portfolio": "المحفظة",
            "Journal": "السجل",
            "Lessons": "الدروس",
            "Settings": "الإعدادات",
        },
        strings={
            "floor_concierge_heading": "AMI CONCIERGE",
            "floor_convene_cta": "اجتماع",
            "convene_confirm": "اجتماع",
            "portfolio_heading": "المحفظة",
            "portfolio_total_value": "القيمة الإجمالية",
            "portfolio_cash": "النقد",
            "journal_heading": "سجل القرارات",
            "journal_filter_all": "الكل",
            "lessons_heading": "الدروس",
            "settings_heading": "الإعدادات",
            "settings_mandate": "التفويض الخاص بي",
        },
    ),
    "ms": LocaleProfile(
        code="ms",
        switcher_native_name="Bahasa Melayu",
        rtl=False,
        tab_labels={
            "Floor": "Floor",
            "Portfolio": "Portfolio",
            "Journal": "Jurnal",
            "Lessons": "Pengajian",
            "Settings": "Tetapan",
        },
        strings={
            "floor_concierge_heading": "AMI CONCIERGE",
            "floor_convene_cta": "KUMPULKAN",
            "convene_confirm": "CONVENE",
            "portfolio_heading": "PORTFOLIO",
            "portfolio_total_value": "NILAI KESELURUHAN",
            "portfolio_cash": "TUNAI",
            "journal_heading": "JURNAL KEPUTUSAN",
            "journal_filter_all": "SEMUA",
            "lessons_heading": "PELAJARAN",
            "settings_heading": "TETAPAN",
            "settings_mandate": "MANDAT SAYA",
        },
    ),
}
