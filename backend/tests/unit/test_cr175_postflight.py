"""CR175 Tier C — the postflight's comparison logic, exercised against failures.

`scripts/promotion/postflight.py` replaces the eyeball step that ended
`/promote-to-alpha` 7 and 7b. Its whole value is that it fails when something is
wrong, so the tests that matter are the ones that break it.

It lives in `scripts/`, not in `backend/`, but its tests live **here** on
purpose: `backend/tests/unit/` is the suite the promotion itself runs at step 1.
A test outside that suite is a test nobody runs, and DEF271 is what that costs —
`prompt_quality_sweep.py` sat dead on import for four days because nothing
executed it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = (Path(__file__).resolve().parents[3]
           / "scripts" / "promotion" / "postflight.py")


def _load():
    spec = importlib.util.spec_from_file_location("postflight", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pf = _load()


def _env_file(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "alpha.env"
    p.write_text(body)
    return p


def _stub_get(payload: dict, status: int = 200):
    def _get(url: str, secret: str | None, timeout: int):
        return status, payload
    return _get


# ── the DEF038/DEF063 case ────────────────────────────────────────────────────

def test_populated_key_not_configured_in_container_fails_and_names_the_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact bug the check exists for: a key set on the Mac whose `${VAR}`
    line is missing from docker-compose.yml's api-alpha block.

    The message must name the compose line. A failure that says only "mismatch"
    sends the operator back to the same manual diff this replaces.
    """
    env = _env_file(tmp_path, "ADANOS_API_KEY_SECONDARY=live-key-value\n"
                              "ADMIN_SECRET=s3cret\n")
    monkeypatch.setattr(pf, "_get", _stub_get({
        "settings_coverage": [
            {"setting": "ADANOS_API_KEY_SECONDARY", "configured": False},
            {"setting": "ADMIN_SECRET", "configured": True},
        ],
    }))

    problems = pf.check_config_parity("http://x", "s3cret", env, 5)
    assert len(problems) == 1
    assert "ADANOS_API_KEY_SECONDARY" in problems[0]
    assert "docker-compose.yml" in problems[0]
    assert "${ADANOS_API_KEY_SECONDARY}" in problems[0]
    # And it never echoes the value it read.
    assert "live-key-value" not in problems[0]


def test_all_populated_keys_configured_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _env_file(tmp_path, "ADANOS_API_KEY=k\nADMIN_SECRET=s3cret\n")
    monkeypatch.setattr(pf, "_get", _stub_get({
        "settings_coverage": [
            {"setting": "ADANOS_API_KEY", "configured": True},
            {"setting": "ADMIN_SECRET", "configured": True},
        ],
    }))
    assert pf.check_config_parity("http://x", "s3cret", env, 5) == []


def test_commented_and_empty_keys_are_not_gaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEF063 parked two keys on purpose. A deliberate park must not read as a
    missing compose line, or the check produces a failure per parked key and
    gets ignored — and an uncommented-but-empty key is absent by the same test
    `bool(settings.x)` applies."""
    env = _env_file(tmp_path,
                    "# SENTRY_DSN=parked-on-purpose\n"
                    "POSTHOG_API_KEY=\n"
                    "ADMIN_SECRET=s3cret\n")
    monkeypatch.setattr(pf, "_get", _stub_get({
        "settings_coverage": [
            {"setting": "SENTRY_DSN", "configured": False},
            {"setting": "POSTHOG_API_KEY", "configured": False},
            {"setting": "ADMIN_SECRET", "configured": True},
        ],
    }))
    assert pf.check_config_parity("http://x", "s3cret", env, 5) == []


def test_compose_level_keys_are_excused_from_the_shared_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`POSTGRES_PASSWORD` and friends are service credentials, never Settings
    fields — excused with a stated reason rather than producing a permanent
    false positive.

    The excuse table is **imported** from `test_config_compose_parity.py`, not
    re-listed: a second hand-maintained copy is the exact CR175 F3 failure, and
    its drift would surface as a permanent false positive. This asserts the
    import path works, so a rename over there fails here instead of silently
    reverting postflight to a shorter list.
    """
    env = _env_file(tmp_path, "POSTGRES_PASSWORD=p\nCF_TUNNEL_TOKEN=t\n"
                              "AMI_ENV=staging\nADMIN_SECRET=s3cret\n")
    monkeypatch.setattr(pf, "_get", _stub_get({
        "settings_coverage": [{"setting": "ADMIN_SECRET", "configured": True}],
    }))
    assert pf.check_config_parity("http://x", "s3cret", env, 5) == []

    excused = pf._keys_without_settings()
    for key in ("POSTGRES_PASSWORD", "CF_TUNNEL_TOKEN", "AMI_ENV",
                "REVENUECAT_IOS_SDK_KEY", "WEBSITE_DB_PASSWORD"):
        assert excused[key], f"{key} lost its stated reason"


def test_a_bool_set_to_false_is_an_off_switch_not_a_missing_compose_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The false positive the first live postflight run produced.

    `SUPPRESS_ANALYST_CONSENSUS=false` is populated in `infra/alpha.env` and
    correctly reports `configured: false` from the container, because for a
    `bool` field `configured` means *the feature is on*, not *the key exists*.
    Flagging it would have failed every promotion on a non-problem — a check
    whose failing state is its normal state, which is the F5 pathology this
    tool exists to remove, reproduced by the tool itself.
    """
    env = _env_file(tmp_path,
                    "SUPPRESS_ANALYST_CONSENSUS=false\n"
                    "USE_REAL_MARKET_DATA=true\n"
                    "ADMIN_SECRET=s3cret\n")
    monkeypatch.setattr(pf, "_get", _stub_get({
        "settings_coverage": [
            {"setting": "SUPPRESS_ANALYST_CONSENSUS", "configured": False},
            {"setting": "USE_REAL_MARKET_DATA", "configured": True},
            {"setting": "ADMIN_SECRET", "configured": True},
        ],
    }))
    assert pf.check_config_parity("http://x", "s3cret", env, 5) == []

    # …but a bool set TRUE and dark in the container is still the real bug.
    monkeypatch.setattr(pf, "_get", _stub_get({
        "settings_coverage": [
            {"setting": "SUPPRESS_ANALYST_CONSENSUS", "configured": False},
            {"setting": "USE_REAL_MARKET_DATA", "configured": False},
            {"setting": "ADMIN_SECRET", "configured": True},
        ],
    }))
    problems = pf.check_config_parity("http://x", "s3cret", env, 5)
    assert len(problems) == 1 and "USE_REAL_MARKET_DATA" in problems[0]


def test_a_container_without_settings_coverage_cannot_run_rather_than_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The trap this whole CR is about. A pre-Tier-B container answers 200 with
    a 9-field body; comparing against it would pass by not looking. That has to
    be `CannotRun`, not a pass — exit 2 and exit 0 must never be confused."""
    env = _env_file(tmp_path, "ADANOS_API_KEY=k\nADMIN_SECRET=s3cret\n")
    monkeypatch.setattr(pf, "_get", _stub_get({"gates": [], "dark_count": 0}))

    with pytest.raises(pf.CannotRun) as exc:
        pf.check_config_parity("http://x", "s3cret", env, 5)
    assert "settings_coverage" in str(exc.value)


# ── identity (F2) ─────────────────────────────────────────────────────────────

def test_unstamped_container_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pf, "_get", _stub_get(
        {"git_sha": "unset", "alpha_tag": "unset"}))
    problems = pf.check_identity("http://x", "s", "abc1234", None, 5)
    assert any("UNSTAMPED" in p for p in problems)


def test_running_a_different_commit_than_was_promoted_is_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The question F2 says nothing could answer."""
    monkeypatch.setattr(pf, "_get", _stub_get(
        {"git_sha": "0000000", "alpha_tag": "alpha-2026-08-12-4"}))
    problems = pf.check_identity(
        "http://x", "s", "abc1234def", "alpha-2026-08-12-4", 5)
    assert len(problems) == 1
    assert "0000000" in problems[0] and "abc1234def" in problems[0]


def test_short_sha_matches_its_own_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """`git rev-parse HEAD` is 40 chars; a stamp may be abbreviated. Treating
    that as a mismatch would make the check fire on every healthy promotion."""
    monkeypatch.setattr(pf, "_get", _stub_get(
        {"git_sha": "abc1234", "alpha_tag": "alpha-2026-08-12-4"}))
    assert pf.check_identity(
        "http://x", "s", "abc1234def5678", "alpha-2026-08-12-4", 5) == []


def test_missing_git_sha_cannot_run_rather_than_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty body would otherwise compare equal to nothing and look fine."""
    monkeypatch.setattr(pf, "_get", _stub_get({}))
    with pytest.raises(pf.CannotRun):
        pf.check_identity("http://x", "s", "abc1234", None, 5)


# ── readiness + market ────────────────────────────────────────────────────────

def test_ready_404_is_a_failure_not_an_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """After a promotion, a missing readiness endpoint means the code you
    shipped did not land."""
    monkeypatch.setattr(pf, "_get", _stub_get({}, status=404))
    problems = pf.check_readiness("http://x", "s", 5)
    assert problems and "did not land" in problems[0]


def test_mock_walk_quote_source_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pf, "_get", _stub_get({"source": "mock_walk"}))
    problems = pf.check_market_data("http://x", 5)
    assert problems and "mock_walk" in problems[0]


@pytest.mark.parametrize("source", ["yfinance", "yahoo"])
def test_both_live_leaf_names_pass(source: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The Flutter LIVE/MOCK pill substring-matches both, so both are live."""
    monkeypatch.setattr(pf, "_get", _stub_get({"source": source}))
    assert pf.check_market_data("http://x", 5) == []


# ── the exclude list must not drift from the promotion's ──────────────────────

def test_tree_check_excludes_match_the_promotion_command() -> None:
    """DEF081 and DEF276 are both "a path the box generates and the Mac does
    not". If this list drifts from `/promote-to-alpha` step 3, the tree check
    reports every such path as drift and stops being read."""
    cmd = (Path(__file__).resolve().parents[3]
           / ".claude" / "commands" / "promote-to-alpha.md").read_text()
    for host_generated in ("audit/", "reports/", "backtest_results/"):
        assert f"--exclude='{host_generated}'" in cmd, (
            f"{host_generated} missing from the promotion's rsync excludes — "
            "rsync --delete would destroy it on the box (DEF081/DEF276)"
        )


# ── the pairing that had no guard (R68-CR175 audit MAJOR-1) ───────────────────

def test_manual_gate_wording_is_not_duplicated() -> None:
    """DEF275's own drift class, recurring inside the round that fixed it.

    `ce6bae87` rewrote `promotion_protocol.md` to match `/promote-to-alpha`
    "step for step", and at that moment it did. 38 minutes later `c539af12`
    fixed F8 — the manual gate asking about a local backend the Mac does not
    have — **in the command only**. The doc kept asking the unanswerable
    question, which is precisely the state DEF275 exists to prevent.

    The auditor caught it; nothing mechanical did. `test_tree_check_excludes_
    match_the_promotion_command` guards the rsync-exclude pairing the same way,
    and this pairing had no sibling.

    The fix is a pointer, not a synchronised copy: two restatements of one
    question drift, and asserting they stay byte-equal would just relocate the
    maintenance. So this asserts the doc does NOT restate the question at all.
    """
    root = Path(__file__).resolve().parents[3]
    doc = (root / "docs" / "initial_specs" / "10_delivery"
           / "promotion_protocol.md").read_text()
    cmd = (root / ".claude" / "commands" / "promote-to-alpha.md").read_text()

    # The command owns the question and must keep asking one.
    assert "(y/n)" in cmd, "the command lost its manual gate entirely"

    # The dead premise must not reappear in either file as a live question.
    # CLAUDE.md and promotion_protocol.md's own "Canonical vs derivative"
    # section both state the Mac runs no backend.
    assert "onboarding on the local backend? (y/n)" not in doc, (
        "promotion_protocol.md is asking the operator to smoke-test a local "
        "backend the Mac does not run — F8, reintroduced. The doc should point "
        "at /promote-to-alpha step 1, not restate its question."
    )
    assert "onboarding on the local backend? (y/n)" not in cmd

    # And the doc must point at the command rather than carry its own copy.
    manual_section = doc.split("**Manual smoke confirmation.**", 1)
    assert len(manual_section) == 2, "the doc lost its manual-gate item"
    body = manual_section[1].split("\n---", 1)[0]
    assert "/promote-to-alpha" in body, (
        "the doc's manual-gate item must point at the command that owns the "
        "wording — a restated copy is a copy that goes stale"
    )
    assert "(y/n)?" not in body and "?\" " not in body, (
        "the doc is restating the question again; that pairing has drifted once"
    )
