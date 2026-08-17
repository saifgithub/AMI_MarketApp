"""DEF328 — a name in `infra/alpha.env` that nothing reads is a silently-dark feature.

`test_config_compose_parity.py` guards the link `Settings` ↔ `docker-compose.yml`.
Nothing guarded the link *before* it: the canonical env file on the Mac ↔ the
variable names compose actually interpolates. So a key can be present, correct,
and paid for, and reach nothing — which is DEF038's and DEF063's outcome arrived
at by a different route.

That is what happened on 2026-08-17. A real Gemini key was added as
`GOOGLE_API_KEY=`; `config.py` declares `google_ai_api_key`, compose forwards
`GOOGLE_AI_API_KEY`, and `llm_gateway` gates registration on
`settings.google_ai_api_key`. Every one of those three was correct. The gateway
even logged its refusal properly (`reason="no GOOGLE_AI_API_KEY in env"`,
CR040's degrade-loudly working exactly as designed) — but that log line only
appears in a container nobody was tailing, so the operator's evidence that the
key worked was that he had pasted it into the file.

The check is derived, not listed (CR175 F3's lesson — a hand-maintained list of
what to check rots, and the field it forgets is the one that matters). A name is
legitimate if it is EITHER a `Settings` field or a `${VAR}` compose interpolates.
Anything else is set on the Mac and read by nobody.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.config import Settings


_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALPHA_ENV = _REPO_ROOT / "infra" / "alpha.env"
_COMPOSE = _REPO_ROOT / "docker-compose.yml"

# Names that legitimately live in the canonical env file and are read by nothing
# on the SERVER, because their consumer is the Flutter client. They are kept here
# as the single store of record for Alpha's credentials; the alternative (a
# second file) is worse. Each needs a reason, and the reason must be "a real
# consumer exists, it just is not this container" — never "unused for now",
# which is the state this test exists to make visible.
_CLIENT_SIDE: dict[str, str] = {
    "REVENUECAT_PUBLIC_SDK_API_KEY": "Flutter SDK init; the backend uses "
                                     "REVENUECAT_SECRET_API_KEY / _WEBHOOK_SECRET",
    "REVENUECAT_IOS_SDK_KEY": "Flutter SDK init (iOS), client-side by design",
    "REVENUECAT_ANDROID_SDK_KEY": "Flutter SDK init (Android), client-side by design",
}


def _assigned_names(env_text: str) -> list[str]:
    """Every `NAME=` assignment, in file order. Comments and blanks skipped."""
    return [
        m.group(1)
        for line in env_text.splitlines()
        if (m := re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=", line))
    ]


def _compose_refs(compose_text: str) -> set[str]:
    """Every `${VAR}` / `${VAR:-default}` / `${VAR:?msg}` compose interpolates."""
    return set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)", compose_text))


def orphan_names(
    env_text: str, compose_text: str, settings_fields: set[str]
) -> list[str]:
    """Names assigned in the env file that neither Settings nor compose reads."""
    refs = _compose_refs(compose_text)
    return [
        name
        for name in _assigned_names(env_text)
        if name not in refs
        and name.lower() not in settings_fields
        and name not in _CLIENT_SIDE
    ]


# ── The mechanism, proven on synthetic input so it runs everywhere ────────────
# `infra/alpha.env` is gitignored, so the corpus test below cannot run in a
# worktree or on a fresh clone. These do, and they are the regression: they
# reproduce DEF328's exact pair of names against a real compose file.


def test_the_wrong_name_is_caught_and_the_right_one_is_not() -> None:
    compose_text = _COMPOSE.read_text(encoding="utf-8")
    fields = set(Settings.model_fields)

    wrong = orphan_names("GOOGLE_API_KEY=AIzaSyFAKE\n", compose_text, fields)
    assert wrong == ["GOOGLE_API_KEY"], (
        "The name DEF328 was actually filed for must be flagged; if this passes "
        "trivially the check has stopped distinguishing the two states."
    )

    right = orphan_names("GOOGLE_AI_API_KEY=AIzaSyFAKE\n", compose_text, fields)
    assert right == [], "GOOGLE_AI_API_KEY is a real Settings field and is forwarded"


def test_comments_and_blank_lines_are_not_names() -> None:
    text = "# GOOGLE_API_KEY=commented-out\n\n   \nVLLM_MODEL=ami-llm\n"
    assert _assigned_names(text) == ["VLLM_MODEL"]


def test_a_client_side_key_is_excused_but_must_carry_a_reason() -> None:
    compose_text = _COMPOSE.read_text(encoding="utf-8")
    fields = set(Settings.model_fields)
    assert orphan_names("REVENUECAT_IOS_SDK_KEY=x\n", compose_text, fields) == []
    for name, reason in _CLIENT_SIDE.items():
        assert reason.strip(), f"{name} is excused with no reason"


def test_compose_ref_forms_are_all_recognised() -> None:
    """`:-default` and `:?error` are both live forms in our compose file."""
    refs = _compose_refs(
        "a: ${PLAIN}\nb: ${WITH_DEFAULT:-x}\nc: ${REQUIRED:?must be set}\n"
    )
    assert refs == {"PLAIN", "WITH_DEFAULT", "REQUIRED"}


# ── The corpus, where the file exists ────────────────────────────────────────


@pytest.mark.skipif(
    not _ALPHA_ENV.exists(),
    reason="infra/alpha.env is gitignored — present only on the promoting machine",
)
def test_the_real_alpha_env_has_no_name_nothing_reads() -> None:
    orphans = orphan_names(
        _ALPHA_ENV.read_text(encoding="utf-8"),
        _COMPOSE.read_text(encoding="utf-8"),
        set(Settings.model_fields),
    )
    assert not orphans, (
        f"{len(orphans)} name(s) in infra/alpha.env are read by nothing: "
        f"{orphans}. Either the name is wrong (DEF328's case — fix the spelling), "
        f"the compose forwarding is missing (DEF038/DEF063's case — add the line "
        f"to the api-alpha environment block), or the consumer is the Flutter "
        f"client (add it to _CLIENT_SIDE with a reason)."
    )
