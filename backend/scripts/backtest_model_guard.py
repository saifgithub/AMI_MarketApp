"""DEF385 — tie the backtest's look-ahead window to the model actually answering.

`--window-start` is the model-cutoff probe's output, and it encodes one
empirical fact: where THAT model's knowledge ends. It used to be a bare number
a human typed, with nothing linking it to the model on the other end, so when
CR211 swapped the served model the guard kept enforcing a boundary five months
too early and the sweep would have reported itself leakage-clean on
contaminated dates.

The reference value the guard compares against is therefore not the typed date
but the probe report (JSON) plus the model's identity: the probe must have been
measured against the `root` the server reports NOW. The alias `id` is reusable
(`ami-llm` was reused across the swap) and is never trusted; `root` is read
from `/v1/models`. Every refusal here is code with no override flag.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx

UNIDENTIFIED_PREFIX = "UNIDENTIFIED"


class ModelGuardError(Exception):
    """A look-ahead-window precondition failed; the caller refuses to proceed."""


def served_identity(base_url: str, *, timeout: float = 15.0) -> str:
    """The served model's `root` (else `id`) from `GET {base_url}/v1/models`.

    Raises ModelGuardError rather than returning a placeholder: a server that
    cannot say what it is serving cannot back a leakage claim.
    """
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/v1/models", timeout=timeout)
        resp.raise_for_status()
        entry = resp.json()["data"][0]
        identity = entry.get("root") or entry.get("id")
    except Exception as exc:  # noqa: BLE001 — any failure means identity unknown
        raise ModelGuardError(
            f"cannot read the served model from {base_url}/v1/models "
            f"({type(exc).__name__}: {exc}) — an unidentifiable model cannot "
            f"back a look-ahead window"
        ) from exc
    if not identity or not isinstance(identity, str):
        raise ModelGuardError(f"{base_url}/v1/models reported no model root or id")
    return identity


def load_probe(path: Path) -> dict:
    if not path.exists():
        raise ModelGuardError(f"cutoff probe report not found: {path}")
    try:
        probe = json.loads(path.read_text())
    except ValueError as exc:
        raise ModelGuardError(f"cutoff probe report is not valid JSON: {path}") from exc
    if not isinstance(probe, dict):
        raise ModelGuardError(f"cutoff probe report is not an object: {path}")
    return probe


def check_probe_window(probe: dict, window_start: date, *, source: str) -> str:
    """Offline checks; returns the probe's recorded model identity.

    The window may start later than the probe's window_start (more conservative)
    but never earlier.
    """
    probe_identity = probe.get("served_identity")
    if not probe_identity or str(probe_identity).startswith(UNIDENTIFIED_PREFIX):
        raise ModelGuardError(
            f"{source} does not record which model it measured "
            f"(served_identity={probe_identity!r}) — it predates DEF385 or the "
            f"server was unidentifiable. Re-run backtest_cutoff_probe.py."
        )
    raw = probe.get("window_start")
    if not raw:
        raise ModelGuardError(
            f"{source} has no window_start — the probe found no valid cutoff"
        )
    try:
        probe_start = date.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise ModelGuardError(f"{source} window_start is not an ISO date: {raw!r}") from exc
    if window_start < probe_start:
        raise ModelGuardError(
            f"--window-start {window_start} is earlier than the probe's "
            f"window_start {probe_start} ({source}) — every date in between is "
            f"inside the model's measured knowledge"
        )
    return str(probe_identity)


def check_served_matches(probe_identity: str, served: str, *, source: str) -> None:
    if probe_identity != served:
        raise ModelGuardError(
            f"the probe backing --window-start measured `{probe_identity}` "
            f"({source}) but the server is answering as `{served}` — the "
            f"window describes a different model. Re-run backtest_cutoff_probe.py "
            f"against the current serve and use its window_start."
        )


def stamp_path(out_dir: Path, batch_id: str) -> Path:
    return out_dir / f"model_{batch_id}.json"


def read_stamp(out_dir: Path, batch_id: str) -> dict | None:
    path = stamp_path(out_dir, batch_id)
    return json.loads(path.read_text()) if path.exists() else None


def write_stamp(out_dir: Path, batch_id: str, *, served: str, probe_source: str,
                probe_window_start: str, window_start: date) -> None:
    """Record the verified model beside the batch; refuse a mixed-model resume."""
    existing = read_stamp(out_dir, batch_id)
    if existing and existing.get("served_model") != served:
        raise ModelGuardError(
            f"batch `{batch_id}` was started on `{existing.get('served_model')}` "
            f"but the server now answers as `{served}` — a resumed batch must "
            f"stay on one model. Use a new --batch-id."
        )
    stamp_path(out_dir, batch_id).write_text(json.dumps({
        "batch_id": batch_id,
        "served_model": served,
        "probe_report": probe_source,
        "probe_window_start": probe_window_start,
        "window_start": window_start.isoformat(),
    }, indent=2) + "\n")
