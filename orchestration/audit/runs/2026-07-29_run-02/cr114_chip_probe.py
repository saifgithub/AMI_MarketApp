"""CR114 blind chip probe — hunt for a chip that raises two flags or none.

Run from .claude/worktrees/audit-REL58/backend/ with the backend venv python.
"""
import sys

sys.path.insert(0, ".")
from app.services.concierge_engine import Q7_CHIPS, _parse_constraints

FLAGS = ["halal", "esg_lite", "no_tobacco_alcohol_gambling", "no_fossil_fuels", "long_only", "liquid_only"]


def flags(text):
    d = _parse_constraints(text)
    return sorted(k for k in FLAGS if d[k])


print("== shipped chips ==")
for c in Q7_CHIPS:
    print(f"{flags(c)!s:35s} <- {c!r}")

print("\n== adversarial ==")
for t in [
    "No hard rules, NEVER fossil fuels",
    "NEVER long positions",
    "ONLY long positions",
    "no alcohol",
    "sharia",
    "",
    "ONLY halal / Sharia-compliant, ONLY ESG-leaning",
]:
    print(f"{flags(t)!s:35s} <- {t!r}")
