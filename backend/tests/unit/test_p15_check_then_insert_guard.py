"""P15-GUARD — check-then-INSERT sites under a real uniqueness constraint carry an IntegrityError handler.

`failure_patterns.md` P15. A function that SELECTs what exists and INSERTs the
rest is correct in one process and raises in two: the read-to-commit gap means
two callers whose reads both land before either commits will both INSERT, and
one loses the constraint.

Second occurrence in CR136 alone — M03 wrote the handler
(`portfolio_snapshot.py:192`), M01 did not — which is what CLAUDE.md's
second-occurrence rule turns into a guard rather than another point fix.

**Why this reads source instead of racing.** The auditor measured 0 races in 60
trials on this stack, because an in-process throttle dict happens to hold the
invariant that nobody wrote down. A runtime test would be flaky-green for the
same reason the bug was invisible: the protection is a deployment fact
(one uvicorn, no `--workers`), and CLAUDE.md's Beta stack is Cloud Run, where
instances share no dict. So this asserts the HANDLER EXISTS, the same way
`test_cr136_dart_parity.py` asserts a cross-boundary contract it cannot execute.

**M01 r2 m3 — the first version of this guard matched `upsert_*` by NAME**, so
it enforced a naming convention rather than the pattern P15 describes, and the
auditor proved it: a check-then-`session.add` that simply was not called
`upsert_*` passed unseen. Two checks now run instead of one:

1. `test_every_upsert_call_site_handles_integrity_error` — the call-site rule,
   kept and renamed to what it actually enforces.
2. `test_no_new_unguarded_check_then_insert_sites` — the SHAPE rule: any
   function that both reads a model and `session.add`s that same model, where
   the model carries a real uniqueness constraint. It found six sites the name
   rule could not see, all outside CR136 and none reviewed here (DEF220).

The inventory in (2) is an exact pin, not a floor, and that is deliberate —
`failure_patterns.md` P6b warns against exact pins on data designed to GROW, and
this is the opposite: a new unguarded check-then-INSERT is exactly the thing
that should stop the build until someone has looked at it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2]
_SERVICES = _BACKEND / "app" / "services"
_MODELS = _BACKEND / "app" / "db" / "models.py"


# Sites the shape rule finds today. Key is (module, function, model) — never a
# line number, which moves for unrelated reasons.
#
# `handled_at_caller` are the two CR136 fixed: the handler wraps the call rather
# than the `session.add`, which is correct (the commit happens in the caller's
# `get_session().__exit__`) and is what this AST rule cannot see from inside the
# callee.
#
# `unreviewed` are pre-existing sites this guard SURFACED and nobody has yet
# analysed — filed as DEF220 rather than fixed blind. Listing them is the point:
# before this rule existed they were not safe, they were invisible.
_HANDLED_AT_CALLER = {
    ("price_history.py", "upsert_daily_bars", "PriceHistoryDailyRow"),
    ("ticker_reference.py", "upsert_reference", "TickerReferenceRow"),
}
_UNREVIEWED = {
    ("auth_service.py", "_upsert_user_device", "UserDeviceRow"),
    ("lessons_service.py", "_check_agent_unlocks", "AgentActivationRow"),
    ("mandate_store.py", "upsert", "MandateRow"),
    ("overlay_store.py", "save_new_version", "OverlayEditCounter"),
    ("reputation_service.py", "_award_badge", "BadgeRow"),
    ("social_context.py", "_cache_write", "SocialSentimentCacheRow"),
}
_KNOWN = _HANDLED_AT_CALLER | _UNREVIEWED


def _collidable_models() -> set[str]:
    """Models where a duplicate INSERT can actually raise.

    A `UniqueConstraint`, a unique `Index`, a `unique=True` column, or a primary
    key with no `default` — that last one is the natural-key case
    (`TickerReferenceRow.symbol`), which collides exactly like an explicit
    constraint. A uuid4-defaulted PK cannot collide and is correctly excluded,
    which is what keeps this rule from flagging every append-only insert.
    """
    tree = ast.parse(_MODELS.read_text(encoding="utf-8"))
    out: set[str] = set()
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        for node in ast.walk(cls):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            kwargs = {kw.arg: kw.value for kw in node.keywords}
            if node.func.id == "UniqueConstraint":
                out.add(cls.name)
            elif node.func.id == "Index":
                if getattr(kwargs.get("unique"), "value", False) is True:
                    out.add(cls.name)
            elif node.func.id == "mapped_column":
                if getattr(kwargs.get("unique"), "value", False) is True:
                    out.add(cls.name)
                if (
                    getattr(kwargs.get("primary_key"), "value", False) is True
                    and "default" not in kwargs
                ):
                    out.add(cls.name)
    return out


def _integrity_guarded_spans(tree: ast.AST) -> list[tuple[int, int]]:
    """Line spans of every `try` body whose handlers name IntegrityError."""
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            names: list[str] = []
            exc = handler.type
            candidates = exc.elts if isinstance(exc, ast.Tuple) else [exc]
            for item in candidates:
                if isinstance(item, ast.Name):
                    names.append(item.id)
                elif isinstance(item, ast.Attribute):
                    names.append(item.attr)
            if "IntegrityError" in names:
                body = node.body
                spans.append((body[0].lineno, body[-1].end_lineno or body[-1].lineno))
    return spans


def _upsert_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id.startswith("upsert_")
    ]


def _modules_calling_upsert() -> list[Path]:
    out = []
    for path in sorted(_SERVICES.glob("*.py")):
        if _upsert_calls(ast.parse(path.read_text(encoding="utf-8"))):
            out.append(path)
    return out


def _check_then_insert_sites() -> set[tuple[str, str, str]]:
    """Every (module, function, model) that reads a model and adds that same
    model, where the model can actually collide. Guarded sites are excluded —
    what this returns is the set still needing a decision."""
    collidable = _collidable_models()
    found: set[tuple[str, str, str]] = set()

    for path in sorted(_SERVICES.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        spans = _integrity_guarded_spans(tree)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            added: dict[str, int] = {}
            read: set[str] = set()
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "add" and node.args:
                        arg = node.args[0]
                        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
                            added.setdefault(arg.func.id, node.lineno)
                    elif (
                        node.func.attr == "get" and node.args
                        and isinstance(node.args[0], ast.Name)
                    ):
                        read.add(node.args[0].id)
                elif (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "select"
                ):
                    for arg in node.args:
                        if isinstance(arg, ast.Name):
                            read.add(arg.id)
                        elif isinstance(arg, ast.Attribute) and isinstance(
                            arg.value, ast.Name
                        ):
                            read.add(arg.value.id)

            for model, line in added.items():
                if model not in read or model not in collidable:
                    continue
                if any(start <= line <= end for start, end in spans):
                    continue        # handled in place, e.g. portfolio_snapshot
                found.add((path.name, fn.name, model))
    return found


def test_the_guard_finds_something_to_check() -> None:
    """Vacuity: a guard that scans nothing passes forever."""
    assert _modules_calling_upsert(), "no upsert_* call sites found — scan broken"
    assert len(_collidable_models()) >= 10, "model parse produced nothing to collide"


@pytest.mark.parametrize(
    "module", _modules_calling_upsert(), ids=lambda p: p.name,
)
def test_every_upsert_call_site_handles_integrity_error(module: Path) -> None:
    """The call-site rule. Named for what it enforces — a convention over
    `upsert_*` helpers — because the shape rule below is what enforces P15."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    spans = _integrity_guarded_spans(tree)

    unguarded = [
        call.lineno for call in _upsert_calls(tree)
        if not any(start <= call.lineno <= end for start, end in spans)
    ]
    assert unguarded == [], (
        f"{module.name}: upsert_* called at line(s) {unguarded} with no enclosing "
        "`except IntegrityError`. See failure_patterns.md P15 — a check-then-INSERT "
        "is correct in one process and raises in two, and a throttle is a deployment "
        "fact, not a guard."
    )


def test_no_new_unguarded_check_then_insert_sites() -> None:
    """The SHAPE rule — P15 as written, not as named.

    An exact pin on purpose: unlike P6b's growing corpora, a new unguarded
    check-then-INSERT is precisely the thing that should stop the build until
    someone has looked at it. Fix it, or add it to `_UNREVIEWED` with a defect
    ID — but do not let it in silently."""
    found = _check_then_insert_sites()

    new = found - _KNOWN
    assert new == set(), (
        f"new unguarded check-then-INSERT site(s): {sorted(new)}. Either wrap the "
        "insert in `except IntegrityError` (failure_patterns.md P15) or record it "
        "in _UNREVIEWED with a defect ID."
    )

    gone = _KNOWN - found
    assert gone == set(), (
        f"site(s) no longer found: {sorted(gone)}. If they were fixed, delete them "
        "from the inventory — a stale entry hides the next real one."
    )
