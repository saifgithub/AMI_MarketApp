#!/usr/bin/env python3
"""Apply the Sharia/observance sensitive-content carve-out (CR083).

Sister to translate_arb_lan.py / translate_content_lan.py — never edits
those scripts. Reads content/i18n/sensitive_keys.json's `exclude` list
(content that must never reach the LLM) and applies it as a thin
pre/post wrapper around the existing translate runs:

  --stage arb --pre
      Pre-seeds the ~10 OBSERVANCE-SENSITIVE ARB keys into
      app_ar.arb / app_ms.arb with their literal EN value, so
      translate_arb_lan.py's skip-unless-overwrite logic leaves them
      untouched. Safe to re-run — never overwrites an existing value.

  --stage content --pre
      Relocates each `whole_file` exclusion (e.g.
      content/ai_coach/islamic_finance.json) out of its directory into
      content/i18n/_excluded_staging/ for the duration of a
      translate_content_lan.py run, so the script's glob never sees it.

  --stage content --post
      Restores whatever --pre relocated.

`strict_review` entries in sensitive_keys.json are NOT touched by this
script — they're translated normally by the existing scripts; the
stricter bar applies later, at verification time
(scripts/i18n_verify_lesson_translation.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SENSITIVE_KEYS_PATH = REPO_ROOT / "content" / "i18n" / "sensitive_keys.json"
STAGING_DIR = REPO_ROOT / "content" / "i18n" / "_excluded_staging"
ARB_DIR = REPO_ROOT / "mobile" / "lib" / "l10n"


def _load_sensitive_keys() -> dict:
    return json.loads(SENSITIVE_KEYS_PATH.read_text(encoding="utf-8"))


def _stage_arb_pre(sensitive: dict) -> int:
    en_data = json.loads((ARB_DIR / "app_en.arb").read_text(encoding="utf-8"))
    changed = 0
    for entry in sensitive.get("exclude", []):
        if entry.get("scope") != "arb_key":
            continue
        ids = entry["ids"]
        for locale in ("ar", "ms"):
            path = ARB_DIR / f"app_{locale}.arb"
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            dirty = False
            for key in ids:
                if key not in en_data:
                    print(f"WARN: {key!r} not found in app_en.arb", file=sys.stderr)
                    continue
                existing = data.get(key)
                if isinstance(existing, str) and existing.strip():
                    continue  # already filled — leave it alone (manual or prior run)
                data[key] = en_data[key]
                dirty = True
                changed += 1
            if dirty:
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=4) + "\n",
                    encoding="utf-8",
                )
                print(f"pre-seeded {len(ids)} key(s) into {path.relative_to(REPO_ROOT)}")
    return changed


def _stage_content_pre(sensitive: dict) -> int:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    moved = 0
    for entry in sensitive.get("exclude", []):
        if entry.get("scope") != "whole_file":
            continue
        src = REPO_ROOT / entry["file"]
        if not src.exists():
            print(f"  {entry['file']}: already relocated or missing, skipping")
            continue
        dest = STAGING_DIR / src.name
        src.rename(dest)
        moved += 1
        print(f"relocated {entry['file']} -> {dest.relative_to(REPO_ROOT)}")
    return moved


def _stage_content_post(sensitive: dict) -> int:
    restored = 0
    for entry in sensitive.get("exclude", []):
        if entry.get("scope") != "whole_file":
            continue
        src = REPO_ROOT / entry["file"]
        staged = STAGING_DIR / Path(entry["file"]).name
        if not staged.exists():
            print(f"  {entry['file']}: nothing staged, skipping")
            continue
        staged.rename(src)
        restored += 1
        print(f"restored {staged.relative_to(REPO_ROOT)} -> {entry['file']}")
    return restored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=["arb", "content"])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pre", action="store_true")
    group.add_argument("--post", action="store_true")
    args = parser.parse_args()

    sensitive = _load_sensitive_keys()

    if args.stage == "arb":
        if args.post:
            print("ARB exclusions only have a --pre step (pre-seed); nothing to do for --post.")
            return 0
        n = _stage_arb_pre(sensitive)
        print(f"Done. {n} key-locale pair(s) pre-seeded.")
        return 0

    if args.pre:
        n = _stage_content_pre(sensitive)
    else:
        n = _stage_content_post(sensitive)
    print(f"Done. {n} file(s) {'relocated' if args.pre else 'restored'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
