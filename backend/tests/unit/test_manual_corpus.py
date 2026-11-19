"""CR022 / CR267 WP-39 — the app-manual corpus: retrieval, truth-to-the-app, citation.

Three things have to hold for the Concierge to be trusted on "how do I use the
app", and each is checked structurally rather than by reading the prose:

  1. RETRIEVAL — the ten fixed how-do-I questions in
     `tests/fixtures/manual/howto_questions.v1.json` each retrieve the one entry
     that answers them, and off-topic questions retrieve nothing.
  2. TRUTH — every entry names only things that exist in the Flutter app at this
     commit: the screens it describes are real files, the ARB keys it names are
     real keys, and every **bold** label in the body is the exact text of one of
     those keys (or a hard-coded label found in a named screen file). A label
     renamed in `app_en.arb` or a screen deleted fails here, not in a tester's hands.
  3. CITATION — a reply drawn from the manual carries a source line appended by
     the runner from the entries it actually supplied (CR038: a prompt asking the
     model to cite is advice, a footer computed in code is a control).

Plus a scope guard: hidden, parked or not-yet-built features (payments, the
developer section, Silent Scout, the per-response Report button and Room thumbs)
and the retired agent titles must never appear in the corpus.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas import AgentId, Mandate
from app.schemas.manual import ManualRetrieval
from app.schemas.one_on_one import OneOnOneSession
from app.services.agent_runner import AgentRunner
from app.services.concierge_prompts import build_concierge_messages, scripted_reply
from app.services.manual_service import (
    CONTENT_MANUAL_DIR,
    MIN_SCORE,
    ManualService,
    manual_citation,
    parse_entry,
    retrieve_manual,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MOBILE_LIB = REPO_ROOT / "mobile" / "lib"
ARB_EN = MOBILE_LIB / "l10n" / "app_en.arb"
FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "manual" / "howto_questions.v1.json"

_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


@pytest.fixture(scope="module")
def service() -> ManualService:
    return ManualService()


@pytest.fixture(scope="module")
def entries(service):
    return service.all_entries()


@pytest.fixture(scope="module")
def arb() -> dict:
    return json.loads(ARB_EN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def howto() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ── corpus shape ─────────────────────────────────────────────────────────


def test_corpus_loads_and_ids_are_unique(entries):
    assert len(entries) >= 20
    ids = [e.id for e in entries]
    assert len(ids) == len(set(ids))
    assert all(i.startswith("manual_") for i in ids)
    assert len(list(CONTENT_MANUAL_DIR.glob("*.en.mdx"))) == len(entries)


def test_entries_are_english_only_and_flag_translation(entries):
    for e in entries:
        assert e.locale_versions == ["en"], e.id
        assert e.translation_pending == ["ar", "ms"], e.id
        assert e.questions and e.short_answer and e.body, e.id
        assert e.screens, f"{e.id} names no screen it describes"


def test_parse_rejects_missing_frontmatter(tmp_path):
    bad = tmp_path / "x.en.mdx"
    bad.write_text("# no frontmatter\n", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        parse_entry(bad)


# ── 1. retrieval ─────────────────────────────────────────────────────────


def test_fixture_is_the_versioned_ten(howto):
    assert howto["version"] == 1
    assert [q["n"] for q in howto["questions"]] == list(range(1, 11))


@pytest.mark.parametrize("n", range(1, 11))
def test_retrieval_returns_the_right_entry_for_each_fixed_question(service, howto, n):
    q = next(x for x in howto["questions"] if x["n"] == n)
    hits = service.retrieve(q["question"])
    assert hits, f"no manual entry retrieved for: {q['question']!r}"
    assert hits[0].entry.id == q["expected_entry"], (
        q["question"], [(h.entry.id, h.score) for h in hits],
    )
    assert hits[0].score >= MIN_SCORE


def test_off_topic_questions_retrieve_nothing(service, howto):
    for question in howto["no_match"]:
        assert service.retrieve(question) == [], question


# ── 2. every entry matches the app ───────────────────────────────────────


def test_the_app_sources_are_present():
    assert ARB_EN.is_file(), "mobile/lib/l10n/app_en.arb missing — the truth check cannot run"


def test_every_screen_an_entry_describes_exists(entries):
    for e in entries:
        for rel in e.screens:
            assert (MOBILE_LIB / rel).is_file(), f"{e.id}: mobile/lib/{rel} does not exist"


def test_every_arb_key_an_entry_names_exists(entries, arb):
    for e in entries:
        for key in e.arb_keys:
            assert key in arb, f"{e.id}: ARB key {key!r} is not in app_en.arb"


def test_every_literal_an_entry_names_is_in_one_of_its_screens(entries):
    for e in entries:
        source = "\n".join((MOBILE_LIB / rel).read_text(encoding="utf-8") for rel in e.screens)
        for lit in e.literals:
            assert lit in source, f"{e.id}: literal {lit!r} not found in its screens"


def test_every_bold_label_is_an_exact_app_label(entries, arb):
    """The body's **LABELS** are the app's labels, verbatim — nothing paraphrased."""
    bad = []
    for e in entries:
        allowed = {str(arb[k]) for k in e.arb_keys if k in arb} | set(e.literals)
        bad += [
            f"{e.id}: **{label}**"
            for label in _BOLD_RE.findall(e.body)
            if label not in allowed
        ]
    assert not bad, "bold labels that are not the text of a declared ARB key or literal:\n" + "\n".join(bad)


def test_tab_names_in_the_corpus_are_the_real_tab_names(arb):
    assert [arb[k] for k in ("floorTabUpper", "portfolioTabUpper", "lessonsTabUpper", "youTabUpper")] == [
        "FLOOR", "PORTFOLIO", "LESSONS", "YOU",
    ]
    nav = (MOBILE_LIB / "screens" / "home_shell.dart").read_text(encoding="utf-8")
    assert "l.floorTabUpper" in nav and "l.youTabUpper" in nav


# ── scope guard: nothing hidden, parked, unbuilt, or off-brand ───────────

_FORBIDDEN = {
    "payments / plans": r"\b(subscription|subscribe|credit pack|top[- ]?up|purchase|billing|upgrade|membership|revenuecat|in-app purchase)\b",
    "dev-only / hidden": r"\b(developer section|silent scout|dev mode|backend switch|AMI_GAMES)\b",
    "the game tab": r"\bGAME tab\b|\bThe Game\b|\bleaderboard\b",
    "not built yet (WP-36, lane/WP36-beta-settings)": r"(report this response|thumbs[- ](up|down|rating)|rate (the|this) room)",
    "retired agent titles": r"\b(PM|Portfolio Manager|Trader|Debator|Market Analyst|News Analyst|Social Media Analyst)\b",
    "'the AI'": r"\bthe AI\b|\bAI (model|assistant)\b",
    "advice": r"\byou should (buy|sell)\b|\bguaranteed\b|\bwill (go up|profit)\b",
}


@pytest.mark.parametrize("name", sorted(_FORBIDDEN))
def test_corpus_never_describes_parked_or_unbuilt_features(entries, name):
    pattern = re.compile(_FORBIDDEN[name], re.IGNORECASE if name != "retired agent titles" else 0)
    for e in entries:
        text = "\n".join([e.title, e.short_answer, e.body, *e.questions])
        m = pattern.search(text)
        assert m is None, f"{e.id}: {name}: {m.group(0)!r}"


def test_the_corpus_says_the_app_is_simulation_only(service):
    entry = service.get("manual_simulation_only")
    assert entry is not None
    answer = entry.short_answer.lower()
    assert "simulation" in answer and "no real trades" in answer and "investment advice" in answer


# ── 3. citation ──────────────────────────────────────────────────────────


class _FakeGateway:
    def __init__(self, reply: str = "Tap CONVENE THE ROOM on the Floor.", stream_error: bool = False):
        self._reply = reply
        self._stream_error = stream_error
        self.system_prompts: list[str] = []

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier, locale="en",
                          max_tokens=1024, meta=None, **_audit):
        self.system_prompts.append(system_prompt)
        if self._stream_error and meta is not None:
            meta["stream_error"] = "HTTP 503"
        yield self._reply


def _session(mandate: Mandate) -> OneOnOneSession:
    return OneOnOneSession(
        id=uuid4(),
        agent_id=AgentId.CONCIERGE,
        started_at=datetime.now(timezone.utc),
        mandate_used=mandate.model_dump(mode="json"),
        locale=mandate.locale,
        user_id=None,
    )


def _run(gateway, mandate, question: str, meta: dict | None = None) -> str:
    runner = AgentRunner(gateway)  # type: ignore[arg-type]

    async def go() -> str:
        out = []
        async for chunk in runner.stream_one_on_one_message(
            session=_session(mandate), history=[], user_message=question, meta=meta,
        ):
            out.append(chunk)
        return "".join(out)

    return asyncio.run(go())


def test_live_reply_carries_the_source_line_for_the_entries_supplied(base_mandate, howto):
    gw = _FakeGateway()
    out = _run(gw, base_mandate, "How do I convene a Room?")
    expected = retrieve_manual("How do I convene a Room?").hits
    assert expected and expected[0].entry.id == "manual_convene_room"
    assert out.startswith("Tap CONVENE THE ROOM on the Floor.")
    assert out.endswith(manual_citation(expected))
    assert "manual_convene_room" in out
    # the retrieved entry's text reached the model, not just its name
    assert "ENTRIES FOR THIS QUESTION" in gw.system_prompts[0]
    assert expected[0].entry.body in gw.system_prompts[0]


@pytest.mark.parametrize("n", range(1, 11))
def test_every_fixed_question_is_cited_end_to_end(base_mandate, howto, n):
    q = next(x for x in howto["questions"] if x["n"] == n)
    out = _run(_FakeGateway(), base_mandate, q["question"])
    assert f"({q['expected_entry']})" in out, out


def test_no_source_line_when_nothing_in_the_manual_matched(base_mandate):
    gw = _FakeGateway(reply="Hello from AMI.")
    out = _run(gw, base_mandate, "hi")
    assert out == "Hello from AMI."
    assert "No manual entry matches this message" in gw.system_prompts[0]


class _MidStreamErrorGateway(_FakeGateway):
    """Streams real content, then dies in-band the way the vLLM gateway reports it."""

    async def stream_chat(self, *, system_prompt, messages, model_tier, locale="en",
                          max_tokens=1024, meta=None, **_audit):
        self.system_prompts.append(system_prompt)
        yield "Tap the Floor tab and then"
        if meta is not None:
            meta["stream_error"] = "HTTP 503"
        yield "[AMI error: HTTP 503 from the upstream provider]"


def test_no_source_line_on_a_reply_cut_short_by_a_stream_error(base_mandate):
    meta: dict = {}
    out = _run(_MidStreamErrorGateway(), base_mandate, "How do I convene a Room?", meta=meta)
    assert "Source: AMI app manual" not in out
    assert "lost the connection" in out
    assert meta.get("stream_error")


def test_error_before_any_content_falls_back_to_the_scripted_manual_answer(base_mandate):
    """The scripted fallback is itself manual-grounded, so it carries exactly one source line."""
    out = _run(_FakeGateway(stream_error=True), base_mandate, "How do I convene a Room?", meta={})
    assert out.count("— Source: AMI app manual") == 1
    assert "manual_convene_room" in out


def test_scripted_reply_answers_from_the_manual_and_cites(base_mandate):
    out = scripted_reply(
        user_message="How do I brief my agent?",
        mandate=base_mandate,
        recent_journal=[],
        unlocked_agents=set(),
        available_lessons=[],
    )
    assert "PROPOSE CHANGE" in out
    assert "— Source: AMI app manual · Brief your agent (manual_brief_agent)" in out


def test_prompt_states_when_the_manual_could_not_be_loaded(base_mandate):
    prompt, _ = build_concierge_messages(
        mandate=base_mandate,
        user_id=None,
        user_message="How do I convene a Room?",
        history=[],
        recent_journal=[],
        unlocked_agents=set(),
        available_lessons=[],
        manual=ManualRetrieval(available=False, hits=[]),
    )
    assert "could not be loaded" in prompt
    assert "from memory" in prompt


def test_prompt_carries_the_static_manual_index_and_the_how_to_rule(base_mandate, entries):
    prompt, _ = build_concierge_messages(
        mandate=base_mandate,
        user_id=None,
        user_message="hi",
        history=[],
        recent_journal=[],
        unlocked_agents=set(),
        available_lessons=[],
    )
    for e in entries:
        assert f"- {e.id} · {e.title}" in prompt
    assert "answer ONLY from the retrieved manual entries" in prompt
    head, tail = prompt.split("FLOOR CONCIERGE CONTEXT", 1)
    assert "MANUAL — INDEX" in head and "ENTRIES FOR THIS QUESTION" in tail


def test_every_arb_key_an_entry_names_is_used_by_one_of_its_screens(entries):
    """A real key is not enough: the entry's screens must actually render it.

    Guards the lazy fix of declaring any matching key — the label has to be one
    the described screens show, so deleting or renaming a use fails the build.
    """
    bad = []
    for e in entries:
        source = "\n".join((MOBILE_LIB / rel).read_text(encoding="utf-8") for rel in e.screens)
        bad += [
            f"{e.id}: {key}"
            for key in e.arb_keys
            if not re.search(rf"\.{re.escape(key)}\b", source)
        ]
    assert not bad, "ARB keys not used by any screen the entry lists:\n" + "\n".join(bad)
