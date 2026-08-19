"""DEF178 — a live secret must not be committable, and this is the check that says so.

A live `sk_live_…` Adanos key was committed verbatim to two checkpoint memos and
pushed to `origin/main`. It was still valid when found (141/250 quota remaining).
Anyone with repo read access could burn the month's quota — silently darkening
the Social Analyst feed, which is CR024's config gate — or get the account
suspended.

DEF178's remediation is four steps and only the last one is preventive:

  1. rotate/revoke the key            — Saiful, external dashboard
  2. rewrite git history + force-push — destructive, operator-approved only
  3. redact the working-tree copies   — done 2026-08-19 (AT:R70)
  4. **a guard, so it cannot happen again**  ← this file

Step 4 is here rather than in a pre-commit hook on purpose. This repo's
governance is explicit that enforcement is convention-only — there is no git
hook and no promotion gate — so a hook would be a control that exists on one
machine and protects nobody who does not have it installed. The suite runs in
CI (`.github/workflows/deploy-beta.yml`) and on every promotion, which is where
a guard actually binds.

**What this does NOT claim.** Redacting the working tree does not unpublish a
pushed secret, and neither does this test. Steps 1 and 2 are what make the
leaked key harmless; this only stops the *next* one. The row says so and so does
this docstring, because a green guard here would otherwise read as "the secret
problem is handled".

**Scope.** Tracked files only, via `git ls-files` — not a filesystem walk. The
thing being prevented is a secret entering *history*, and an untracked scratch
file is not on that path. Deriving the list from git also means a new directory
is covered the moment it is tracked, with nothing to remember (CR175 F3).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]

#: Live-secret shapes, each anchored on a vendor prefix rather than on entropy
#: alone. Entropy heuristics on a repo this size produce false positives on
#: hashes, UUIDs and base64 fixtures, and a guard that cries wolf is the thing
#: DEF277 is about — so this stays specific and is widened by adding a vendor,
#: deliberately, when one arrives.
_SECRET_SHAPES: dict[str, re.Pattern] = {
    "Adanos live key (DEF178)": re.compile(r"sk_live_[A-Za-z0-9_-]{12,}"),
    "Anthropic API key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "OpenAI API key": re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    "Google API key": re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b"),
    "Slack token": re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    "AWS access key id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

#: Files that legitimately contain a matching STRING and no secret. Each entry
#: is a path plus the reason, so a future reader can tell an excuse from a fact.
#: This list is asserted to stay small; it is not a place to park a real leak.
_ALLOWED: dict[str, str] = {
    "backend/tests/unit/test_def178_no_live_secret_is_committed.py":
        "this file — it contains the patterns by definition",
}

_SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
                  ".ttf", ".otf", ".woff", ".woff2", ".zip", ".gz", ".keystore",
                  ".jks", ".mp3", ".wav", ".m4a", ".mp4", ".aab", ".apk")


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=_REPO, capture_output=True, text=True, check=True
    ).stdout
    return [f for f in out.split("\0") if f and not f.endswith(_SKIP_SUFFIXES)]


def scan() -> list[str]:
    """Every tracked file carrying something shaped like a live secret."""
    findings: list[str] = []
    for rel in _tracked_files():
        if rel in _ALLOWED:
            continue
        p = _REPO / rel
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError, FileNotFoundError):
            continue
        for label, pattern in _SECRET_SHAPES.items():
            m = pattern.search(text)
            if m:
                # Report WHERE and WHAT KIND. Never the value — a guard that
                # prints the secret it caught has published it again, into CI
                # logs this time.
                line = text[: m.start()].count("\n") + 1
                findings.append(f"{rel}:{line}  {label}")
    return findings


def test_no_tracked_file_contains_a_live_secret():
    findings = scan()
    assert not findings, (
        "a live-secret shape is present in tracked files:\n"
        + "".join(f"    {f}\n" for f in findings)
        + "\n"
        "DEF178: an `sk_live_…` Adanos key reached origin/main this way and was "
        "still valid when found.\n"
        "\n"
        "If it is a REAL secret: rotate it first, then remove it. Deleting the "
        "line is not enough — anything already pushed stays in history and needs "
        "git-filter-repo plus an operator-approved force-push.\n"
        "If it is a placeholder or fixture: give it an obviously-fake value, or "
        "add the path to _ALLOWED with the reason. Do not widen the pattern."
    )


def test_the_scan_actually_reads_the_repo():
    """Vacuity pin. A broken `git ls-files` call, a wrong repo root or an
    over-eager skip list would make the test above pass over nothing —
    the P21 shape, and the one failure mode a green secret-scanner hides."""
    files = _tracked_files()
    assert len(files) > 500, f"only {len(files)} tracked files scanned — the sweep is broken"
    assert any(f.startswith("backend/app/") for f in files)
    assert any(f.startswith("docs/") for f in files)
    assert any(f.endswith(".md") for f in files), (
        "no markdown scanned — DEF178's leak was in a .md checkpoint memo, so "
        "a sweep that skips markdown would have missed the actual incident"
    )


def test_the_patterns_catch_the_key_that_actually_leaked():
    """Pins the regexes against the real shape, so a future edit cannot loosen
    them into a check that matches nothing. Values here are synthetic."""
    adanos = _SECRET_SHAPES["Adanos live key (DEF178)"]
    assert adanos.search("ADANOS_API_KEY=sk_live_9c28abcdef0123456789")
    # The row records that `sk_live_test` in test_def099_merge_billing.py is a
    # placeholder, NOT the live key. The guard must tell them apart, or it
    # fires on a correct fixture forever (DEF277).
    assert not adanos.search("sk_live_test")

    assert _SECRET_SHAPES["Anthropic API key"].search("sk-ant-api03-" + "a" * 24)
    assert _SECRET_SHAPES["AWS access key id"].search("AKIAIOSFODNN7EXAMPLE")
    assert _SECRET_SHAPES["private key block"].search("-----BEGIN RSA PRIVATE KEY-----")


def test_the_allowlist_stays_small_and_explains_itself():
    """An allowlist is how a secret scanner dies: one entry at a time, each
    reasonable, until it covers the file with the secret in it."""
    assert len(_ALLOWED) <= 3, (
        f"the secret-scan allowlist has grown to {len(_ALLOWED)} entries. Each one "
        "is a file this guard no longer protects. Prefer an obviously-fake value "
        "in the file over an exemption."
    )
    for path, reason in _ALLOWED.items():
        assert len(reason) > 15, f"{path} is exempted without a real reason"
