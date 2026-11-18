"""CR275 (CR267 WP-21a) — the Room decides blind: the Street's view never reaches an agent.

The fact sheet carries the sell-side's rating, price targets, rating split and
per-firm action tape (`fundamentals.fetch_live_fundamentals`, CR260's
`analyst_targets`). They stay on the profile dict because post-verdict code
reads them (`room_runner._analyst_view_from_profile`, and WP-21b's comparison).
They must not reach any desk agent, the CIO/PM, or any judge: the Beta
programme scores the Room against the Street, and a Room that was shown the
Street cannot be scored against it.

`blind_profile` is the one function every prompt-side reader of the profile
goes through (`room_prompts._format_profile`, the sole renderer behind
`build_room_messages` and `build_risk_officer_messages`). Matching is by the
`analyst_` prefix, in both the values and `field_state`, so a Street field
added later is withheld by default rather than leaking until someone remembers.
Deliberately NOT the CR035 `suppress_analyst_consensus` flag: that is an
off-by-default ablation toggle that also drops the data from the profile.
"""

from __future__ import annotations

from typing import Any

STREET_VIEW_PREFIX = "analyst_"


def is_street_view_key(key: str) -> bool:
    return key.startswith(STREET_VIEW_PREFIX)


def blind_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """A copy of `profile` without any Street-view value or `field_state` entry.

    Shallow on purpose: the caller only reads it, and the original — which the
    post-verdict code still needs — is never mutated.
    """
    blind = {k: v for k, v in profile.items() if not is_street_view_key(k)}
    field_state = profile.get("field_state")
    if isinstance(field_state, dict):
        blind["field_state"] = {
            k: v for k, v in field_state.items() if not is_street_view_key(k)
        }
    return blind
