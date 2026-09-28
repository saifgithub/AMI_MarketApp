"""Prompt-variant A/B for Room agents — swap whole personas in-process.

CR247's phases change agent personas, and benchmarking a prompt change needs
the Room to run with a candidate persona WITHOUT editing backend files. This
module loads a named variant (``benchmarks/<name>/prompts/<agent_id>.md``) and
installs it for the duration of one benchmark run.

Hook point: ``app.services.agent_prompts.load_base_prompt``
(backend/app/services/agent_prompts.py:27). Every Room agent's persona flows
through exactly one chain — ``room_runner`` calls
``room_prompts.build_room_messages`` (room_runner.py:7498 and :8105), which
calls ``agent_prompts.build_agent_prompt`` (room_prompts.py:30/:1666), which
calls ``load_base_prompt`` (agent_prompts.py:98) for the
``content/agents/<agent_id>.md`` body. Replacing that one module attribute
swaps the persona and nothing else: the fact sheet, mandate snapshot,
transcript, stance/GAPS envelopes and per-phase format instructions all live
in the "Room addition" block that ``build_room_messages`` appends AFTER the
base (room_prompts.py:1970), so they are untouched. This satisfies the v1
constraint that the real content is carried by ``system_prompt`` while
``messages`` is a placeholder — the override lands squarely in the
``system_prompt`` path.

``load_base_prompt`` is ``lru_cache``-d, but the cache is never consulted
while the override is installed: the patch replaces the module attribute
outright, and ``build_agent_prompt`` resolves the name through its module
globals at call time, so every import site (including
``room_prompts``' from-import) sees the wrapper. On exit the ORIGINAL cached
function object is restored verbatim — warm cache and all — so no
cache-clearing is needed and pre-existing state survives.

Fail-loud guarantee: a silent no-op override would score the backend-default
prompt under a variant's label, which is worse than no benchmark at all. So
installation verifies, BEFORE the wrapped block runs:

1. the hook attribute exists and is callable;
2. ``room_prompts.build_room_messages`` still composes through
   ``agent_prompts.build_agent_prompt`` (module-attribute identity — if the
   backend re-wires assembly to bypass it, this fails here, not downstream);
3. a real probe render through ``build_room_messages`` for EVERY overridden
   agent contains the override text, and a probe of one non-overridden agent
   still contains its own content-file persona (the wrapper did not clobber
   the pass-through).

Any failure raises ``PromptOverrideError`` naming the agent and the hook
point, with the original loader already restored. ``try/finally`` guarantees
restoration on every exit path, including exceptions inside the block.

Concurrency constraint: the override is PROCESS-WIDE for the wrapped block.
``RoomRunner`` is async and the toolkit convenes concurrently across tickers,
so benchmarks must vary prompts per benchmark FILE (one ``apply_overrides``
block per benchmark run), never per concurrent arm within one block.

Stdlib-only at module level; backend modules are imported lazily inside the
functions so importing this module never requires ``backend/`` on sys.path.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager, nullcontext
from datetime import UTC
from pathlib import Path
from types import ModuleType
from typing import Any

VARIANTS_DIR_NAME = "prompts"

BACKEND_DEFAULT_VARIANT = "backend-default"

_LOADER_HOOK = "app.services.agent_prompts.load_base_prompt"
_COMPOSER_HOOK = "app.services.room_prompts.build_room_messages"
_BUILDER_HOOK = "app.services.agent_prompts.build_agent_prompt"

_PROBE_TICKER = "ZZZ"


class PromptOverrideError(RuntimeError):
    """A persona override could not be installed or verified.

    Raised at install time — never during the benchmark run — when the
    backend's prompt-assembly path has changed such that the override cannot
    take effect. The message names the agent and the hook point that no
    longer exists. Silent no-op overrides are the one unacceptable outcome.
    """


def _backend_modules() -> tuple[ModuleType, ModuleType, Any, Any]:
    try:
        from app.schemas import TWELVE_AGENT_IDS, AgentId
        from app.services import agent_prompts, room_prompts
    except ImportError as exc:
        raise PromptOverrideError(
            f"prompt_lab cannot import the backend prompt-assembly modules "
            f"(expected app.services.agent_prompts / app.services.room_prompts "
            f"importable with backend/ on sys.path): {exc}"
        ) from exc
    return agent_prompts, room_prompts, AgentId, TWELVE_AGENT_IDS


def _valid_room_agent_ids() -> frozenset[str]:
    _, _, _, twelve = _backend_modules()
    return frozenset(a.value for a in twelve)


def load_variant(name: str, *, benchmarks_dir: Path) -> dict[str, str] | None:
    """Load a named prompt variant: {agent_id: persona_text} for each .md.

    ``"backend-default"`` means no overrides and returns None. Any other name
    reads ``benchmarks_dir/<name>/prompts/<agent_id>.md`` for every .md
    present. Raises FileNotFoundError naming the directory when the variant
    dir does not exist, and ValueError listing the unknown stems when a
    filename is not one of the twelve Room agent ids (the valid set comes
    from the backend's own ``app.schemas.TWELVE_AGENT_IDS``, not a hand-typed
    list, so a renamed or added agent fails here rather than silently
    overriding nothing).
    """
    if name == BACKEND_DEFAULT_VARIANT:
        return None
    variant_dir = benchmarks_dir / name / VARIANTS_DIR_NAME
    if not variant_dir.is_dir():
        raise FileNotFoundError(
            f"Prompt variant directory not found: {variant_dir}. "
            f"Expected {VARIANTS_DIR_NAME}/ under benchmarks/{name}/, or use "
            f"{BACKEND_DEFAULT_VARIANT!r} for no overrides."
        )
    valid = _valid_room_agent_ids()
    overrides: dict[str, str] = {}
    unknown: list[str] = []
    for path in sorted(variant_dir.glob("*.md")):
        if path.stem not in valid:
            unknown.append(path.stem)
            continue
        overrides[path.stem] = path.read_text(encoding="utf-8")
    if unknown:
        raise ValueError(
            f"Unknown Room agent id(s) in {variant_dir}: "
            f"{', '.join(sorted(unknown))}. Valid ids (from "
            f"app.schemas.TWELVE_AGENT_IDS): {', '.join(sorted(valid))}."
        )
    return overrides


def apply_overrides(overrides: dict[str, str] | None) -> AbstractContextManager[None]:
    """Install whole-persona overrides for the wrapped block; restore after.

    None or {} is a no-op context manager. Otherwise returns a context
    manager that patches ``app.services.agent_prompts.load_base_prompt`` so
    each named agent's Room persona is the supplied text for the duration of
    the block, verifies by probe render that the override genuinely reaches
    the assembled ``system_prompt``, and restores the original loader in a
    ``finally``. Raises ``PromptOverrideError`` (with the original loader
    already restored) if any verification fails.
    """
    if not overrides:
        return nullcontext()
    return _install(dict(overrides))


def _probe_mandate() -> Any:
    from datetime import datetime
    from uuid import uuid4

    from app.schemas.mandate import (
        Compliance,
        Horizon,
        LearningStyle,
        Mandate,
        Plan,
        PrimaryGoal,
        RiskComponents,
    )
    from app.schemas.mandate import (
        Path as MandatePath,
    )

    return Mandate(
        user_id=uuid4(),
        version=1,
        display_name="Prompt Lab Probe",
        locale="en",
        timezone="UTC",
        primary_goal=PrimaryGoal.LONG_TERM_WEALTH,
        horizon=Horizon.LONG,
        target_outcome=None,
        path=MandatePath.LONG_HORIZON,
        risk_score=3,
        risk_components=RiskComponents(
            drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3
        ),
        risk_quotes=[],
        max_drawdown_pct=30,
        compliance=Compliance(long_only=True, liquid_only=True),
        learning_style=LearningStyle.QUICK,
        plan=Plan.TRADER,
        trial_expires_at=None,
        credit_balance=150,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _probe_render(room_prompts: ModuleType, agent_id: Any, mandate: Any) -> str:
    system_prompt, _ = room_prompts.build_room_messages(
        agent_id=agent_id,
        mandate=mandate,
        user_id=None,
        ticker=_PROBE_TICKER,
        profile={"ticker": _PROBE_TICKER, "field_state": {}},
        transcript=[],
    )
    return system_prompt


@contextmanager
def _install(overrides: dict[str, str]):
    agent_prompts, room_prompts, agent_id_type, twelve = _backend_modules()
    valid = {a.value for a in twelve}

    blank = sorted(k for k, v in overrides.items() if not v.strip())
    if blank:
        raise ValueError(
            f"Empty persona text for: {', '.join(blank)}. A blank override "
            f"would probe-pass vacuously and run the Room with no persona."
        )
    unknown = sorted(k for k in overrides if k not in valid)
    if unknown:
        raise PromptOverrideError(
            f"Override names non-Room agent id(s): {', '.join(unknown)} — the "
            f"hook point {_LOADER_HOOK} is never called for them, so the "
            f"override would silently never fire. Valid ids: "
            f"{', '.join(sorted(valid))}."
        )

    original_loader = getattr(agent_prompts, "load_base_prompt", None)
    if not callable(original_loader):
        raise PromptOverrideError(
            f"Hook point {_LOADER_HOOK} no longer exists or is not callable — "
            f"the backend's prompt-assembly path has changed; re-derive the "
            f"hook before running any variant."
        )
    composer = getattr(room_prompts, "build_room_messages", None)
    if not callable(composer):
        raise PromptOverrideError(
            f"Hook point {_COMPOSER_HOOK} no longer exists — cannot verify "
            f"overrides against the Room's assembly path."
        )
    builder = getattr(agent_prompts, "build_agent_prompt", None)
    if not callable(builder) or getattr(room_prompts, "build_agent_prompt", None) is not builder:
        raise PromptOverrideError(
            f"{_COMPOSER_HOOK} no longer composes through {_BUILDER_HOOK} "
            f"(module-attribute identity check failed) — patching "
            f"{_LOADER_HOOK} would not reach Room prompts."
        )

    def patched(agent_id: Any) -> str:
        key = getattr(agent_id, "value", agent_id)
        if key in overrides:
            return overrides[key]
        return original_loader(agent_id)

    # Capturing the baseline through the original loader doubles as an
    # existence check: a missing content/agents/<id>.md fails loudly here
    # (FileNotFoundError from the backend) instead of mid-benchmark.
    for key in overrides:
        original_loader(agent_id_type(key))
    agent_prompts.load_base_prompt = patched
    try:
        mandate = _probe_mandate()
        for key, text in overrides.items():
            try:
                rendered = _probe_render(room_prompts, agent_id_type(key), mandate)
            except PromptOverrideError:
                raise
            except Exception as exc:
                raise PromptOverrideError(
                    f"Probe render through {_COMPOSER_HOOK} failed for "
                    f"{key!r} — cannot verify the override takes effect: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            if text not in rendered:
                raise PromptOverrideError(
                    f"Probe render for {key!r} does not contain the override "
                    f"text: hook point {_LOADER_HOOK} no longer feeds "
                    f"{_COMPOSER_HOOK}. The override cannot take effect."
                )
        untouched = next((k for k in sorted(valid) if k not in overrides), None)
        if untouched is not None:
            control = original_loader(agent_id_type(untouched))
            rendered = _probe_render(room_prompts, agent_id_type(untouched), mandate)
            if control not in rendered:
                raise PromptOverrideError(
                    f"Control probe for non-overridden {untouched!r} lost its "
                    f"backend-default persona — the wrapper at {_LOADER_HOOK} "
                    f"is clobbering pass-through agents."
                )
    except BaseException:
        agent_prompts.load_base_prompt = original_loader
        raise

    try:
        yield
    finally:
        agent_prompts.load_base_prompt = original_loader
