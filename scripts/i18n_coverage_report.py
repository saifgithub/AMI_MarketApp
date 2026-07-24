#!/usr/bin/env python3
"""Generate content/i18n/coverage_status.md — per-tier/per-locale AR+MS
translation completion (CR083). Read-only reporting except for one
deliberate side effect: it syncs each EN lesson's `locale_versions`
frontmatter array from which translated sibling files actually exist on
disk.

Why the sync is needed: translate_lessons_lan.py writes `locale_versions`
only into the *translated* file's own frontmatter (<id>.ar.mdx /
<id>.ms.mdx), never back into the source <id>.en.mdx. But
lessons_service.py's catalogue() reads `locale_versions` only from the
EN file to decide whether a lesson appears in the ar/ms catalogue.
Without this sync, translated lessons would sit on disk invisible to
the app. This is content-metadata bookkeeping, not application logic.

Run: backend/.venv/bin/python scripts/i18n_coverage_report.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARB_DIR = REPO_ROOT / "mobile" / "lib" / "l10n"
CONTENT_DIR = REPO_ROOT / "content"
LESSONS_DIR = CONTENT_DIR / "lessons"
I18N_DIR = CONTENT_DIR / "i18n"
LOCALES = ("ar", "ms")

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
LOCALE_VERSIONS_RE = re.compile(r"^locale_versions:\s*(\[.*?\])\s*$", re.MULTILINE)


# ---------- Tier 1: ARB --------------------------------------------------

def _arb_coverage() -> dict:
    en = json.loads((ARB_DIR / "app_en.arb").read_text(encoding="utf-8"))
    en_keys = [k for k in en if not k.startswith("@") and k != "appTitle"]
    out = {"total": len(en_keys), "locales": {}}
    for locale in LOCALES:
        path = ARB_DIR / f"app_{locale}.arb"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        filled = sum(1 for k in en_keys if isinstance(data.get(k), str) and data[k].strip())
        out["locales"][locale] = {"filled": filled, "missing": len(en_keys) - filled}
    return out


# ---------- Tier 2: glossary / ai_coach / daily_challenges ---------------

def _ids_of(records) -> set:
    return {r.get("id") for r in records if isinstance(r, dict) and r.get("id")}


def _glossary_coverage() -> dict:
    en_path = CONTENT_DIR / "glossary" / "terms.en.json"
    en_ids = _ids_of(json.loads(en_path.read_text(encoding="utf-8"))) if en_path.exists() else set()
    out = {"total": len(en_ids), "locales": {}}
    for locale in LOCALES:
        path = CONTENT_DIR / "glossary" / f"terms.{locale}.json"
        ids = _ids_of(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else set()
        out["locales"][locale] = {"filled": len(en_ids & ids), "missing": len(en_ids - ids)}
    return out


def _subdir_json_coverage(subdir: str) -> dict:
    """For ai_coach / daily_challenges: content/<subdir>/*.json (EN, flat)
    vs content/<subdir>/<locale>/*.json (translated, subdir)."""
    en_files = sorted((CONTENT_DIR / subdir).glob("*.json"))
    per_file = {}
    total_ids = 0
    for f in en_files:
        try:
            ids = _ids_of(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
        per_file[f.name] = ids
        total_ids += len(ids)
    out = {"total": total_ids, "files": len(per_file), "locales": {}}
    for locale in LOCALES:
        filled = 0
        for fname, en_ids in per_file.items():
            loc_path = CONTENT_DIR / subdir / locale / fname
            loc_ids = _ids_of(json.loads(loc_path.read_text(encoding="utf-8"))) if loc_path.exists() else set()
            filled += len(en_ids & loc_ids)
        out["locales"][locale] = {"filled": filled, "missing": total_ids - filled}
    return out


# ---------- Tier 3: lessons (+ locale_versions sync) ---------------------

def _sync_lesson_locale_versions() -> list[str]:
    """Rewrite each EN lesson's locale_versions to match which translated
    sibling files exist on disk. Returns list of lesson ids changed."""
    changed = []
    for en_path in sorted(LESSONS_DIR.glob("*.en.mdx")):
        lesson_id = en_path.name[: -len(".en.mdx")]
        text = en_path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            print(f"WARN: {en_path.name} has no frontmatter block", file=sys.stderr)
            continue
        fm = m.group(1)
        present = ["en"] + [
            loc for loc in LOCALES
            if (LESSONS_DIR / f"{lesson_id}.{loc}.mdx").exists()
        ]
        lv_match = LOCALE_VERSIONS_RE.search(fm)
        current = json.loads(lv_match.group(1)) if lv_match else ["en"]
        if sorted(current) == sorted(present):
            continue
        new_fm = (
            LOCALE_VERSIONS_RE.sub(f"locale_versions: {json.dumps(present)}", fm)
            if lv_match
            else fm + f"\nlocale_versions: {json.dumps(present)}"
        )
        new_text = text[: m.start(1)] + new_fm + text[m.end(1):]
        en_path.write_text(new_text, encoding="utf-8")
        changed.append(lesson_id)
    return changed


def _lessons_coverage() -> dict:
    en_files = sorted(LESSONS_DIR.glob("*.en.mdx"))
    out = {"total": len(en_files), "locales": {}}
    for locale in LOCALES:
        filled = sum(
            1 for f in en_files
            if (LESSONS_DIR / f"{f.name[:-len('.en.mdx')]}.{locale}.mdx").exists()
        )
        out["locales"][locale] = {"filled": filled, "missing": len(en_files) - filled}
    return out


# ---------- Report --------------------------------------------------------

def _fmt_tier(name: str, cov: dict, extra: str = "") -> str:
    lines = [f"### {name} — {cov['total']} total{extra}", "", "| Locale | Filled | Missing | % |", "|---|---|---|---|"]
    for locale, d in cov["locales"].items():
        pct = 100.0 * d["filled"] / cov["total"] if cov["total"] else 0.0
        lines.append(f"| {locale} | {d['filled']} | {d['missing']} | {pct:.1f}% |")
    return "\n".join(lines)


def main() -> int:
    arb = _arb_coverage()
    glossary = _glossary_coverage()
    ai_coach = _subdir_json_coverage("ai_coach")
    daily_challenges = _subdir_json_coverage("daily_challenges")
    changed = _sync_lesson_locale_versions()
    lessons = _lessons_coverage()

    report = [
        "# i18n coverage status",
        "",
        "GENERATED by `scripts/i18n_coverage_report.py` — do not hand-edit.",
        "",
        _fmt_tier("Tier 1 — ARB (mobile/lib/l10n)", arb),
        "",
        _fmt_tier("Tier 2a — Glossary", glossary),
        "",
        _fmt_tier("Tier 2b — AI Coach", ai_coach, f" across {ai_coach['files']} file(s)"),
        "",
        _fmt_tier("Tier 2c — Daily Challenges", daily_challenges, f" across {daily_challenges['files']} file(s)"),
        "",
        _fmt_tier("Tier 3 — Lessons", lessons),
        "",
    ]
    if changed:
        report.append(f"`locale_versions` synced this run for {len(changed)} lesson(s): {', '.join(changed[:10])}"
                       + (f" (+{len(changed) - 10} more)" if len(changed) > 10 else ""))
    else:
        report.append("`locale_versions` already in sync with what's on disk.")
    report.append("")

    out_path = I18N_DIR / "coverage_status.md"
    out_path.write_text("\n".join(report), encoding="utf-8")
    print(f"Wrote {out_path.relative_to(REPO_ROOT)}")
    if changed:
        print(f"Synced locale_versions for {len(changed)} lesson(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
