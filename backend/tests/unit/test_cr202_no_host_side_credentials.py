"""CR202 — this host stores no third-party credential, and re-adding one is deliberate.

CR202's benefit is not the code it deleted; it is a property: **AMI's backend
holds no user's brokerage credential.** A property that lives only in a commit
message erodes the first time someone adds a column in a hurry, and CR040's
house lesson is that a rule which is only written down is not a control.

The cost of NOT having this guard is measured, not hypothetical. One credential
pair, held on the host, produced four security defects — none of them the same
bug, all of them consequences of holding it:

  DEF044  stored cleartext in Postgres
  DEF181  leaked into http_audit.request_body, bypassing DEF044's own control
  DEF182  SECRET_KEY reused as the encryption key, and the crypto failed OPEN
  DEF185  an empty SECRET_KEY passed the boot check, disabling that encryption

Each was fixed properly. Each was a control built around a secret we did not
need to keep. The generalisation is the point: a secret we hold is a secret we
can leak, and every control we wrap around it is a new surface that can fail.
Before adding a credential column, the question to answer is whether the
*device* can hold it instead — as it now does for Alpaca.

Pinned by `(table, column)`, which is an identity. DEF122's lesson was that
`file:line` is a *coordinate*: it drifts on unrelated edits, the guard cries
wolf, and people learn to skim past it. A table/column pair does not move when
someone inserts a field above it.

This is a floor, not a prohibition. If a credential genuinely must live on the
host, add it here with the reason — the failure is meant to make that a
decision someone made, not one they backed into.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_MODELS = Path(__file__).resolve().parents[2] / "app" / "db" / "models.py"

_CREDENTIAL_SHAPED = re.compile(r"(secret|token|api[_-]?key|password|credential)", re.I)

# (table, column) -> why this one is not a stored credential.
_ALLOWED: dict[tuple[str, str], str] = {
    ("users", "token_version"): (
        "CR125 — an integer revocation counter. Bumping it invalidates issued "
        "bearers; it is not itself a secret and opens nothing."
    ),
    ("llm_audit", "input_tokens"): "LLM usage count, not a credential.",
    ("llm_audit", "output_tokens"): "LLM usage count, not a credential.",
    ("llm_audit", "cache_read_tokens"): "LLM usage count, not a credential.",
    ("llm_audit", "cache_write_tokens"): "LLM usage count, not a credential.",
}


def _credential_shaped_columns() -> set[tuple[str, str]]:
    """Every credential-shaped column name in models.py, tagged with its table."""
    tree = ast.parse(_MODELS.read_text(encoding="utf-8"))
    found: set[tuple[str, str]] = set()

    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue

        table = cls.name
        for node in cls.body:
            if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "__tablename__" for t in node.targets
            ):
                value = getattr(node.value, "value", None)
                if isinstance(value, str):
                    table = value

        for node in cls.body:
            name: str | None = None
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                name = node.target.id
            elif (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                name = node.targets[0].id

            if name and not name.startswith("__") and _CREDENTIAL_SHAPED.search(name):
                found.add((table, name))

    return found


def test_no_new_credential_column_is_added_without_a_decision():
    found = _credential_shaped_columns()

    new = found - set(_ALLOWED)
    assert new == set(), (
        f"credential-shaped column(s) added to models.py: {sorted(new)}.\n\n"
        "CR202 removed host-side custody of the user's Alpaca key because "
        "holding it produced DEF044, DEF181, DEF182 and DEF185 — four "
        "defects, one credential. Before adding this column, answer whether "
        "the DEVICE can hold the secret instead (see "
        "mobile/lib/services/alpaca/alpaca_credential_store.dart). If it "
        "genuinely must live here, add it to _ALLOWED with the reason, "
        "encrypt it at rest with EncryptedString, and read DEF182 first."
    )


def test_the_pin_has_no_stale_entries():
    """A stale allow-list entry hides the next real one — DEF122's other half."""
    found = _credential_shaped_columns()

    gone = set(_ALLOWED) - found
    assert gone == set(), (
        f"allow-listed column(s) no longer exist: {sorted(gone)}. Remove them "
        "from _ALLOWED — a pin that describes a column nobody has is noise "
        "that makes the real entries harder to read."
    )


def test_the_alpaca_credential_columns_are_actually_gone():
    """The specific thing CR202 removed, named rather than implied.

    The generic guard above would pass if someone re-added these under the
    allow-list; this one says the quiet part out loud, so restoring host-side
    Alpaca storage has to argue with a test that mentions it by name.
    """
    source = _MODELS.read_text(encoding="utf-8")
    tree = ast.parse(source)

    declared: set[str] = set()
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        for node in cls.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                declared.add(node.target.id)

    for column in (
        "alpaca_access_token",
        "alpaca_refresh_token",
        "alpaca_linked_at",
        "alpaca_auth_mode",
    ):
        assert column not in declared, (
            f"{column} is back on a model. The user's Alpaca credential lives "
            "on their device (CR202); this host has nothing to store and "
            "nothing to encrypt. If that decision has changed, change it in "
            "the CR202 doc and here together — not by adding a column."
        )
