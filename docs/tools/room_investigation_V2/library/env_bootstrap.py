"""Environment bootstrap for the room_investigation_V2 toolkit (DESIGN.md §4.1).

Why this exists: v1's live 2026-09-26 failure — `backend/.env` does not exist,
and `Settings.model_config`'s `env_file=".env"` resolves relative to CWD, so
running from `backend/` silently loaded NOTHING and fell back to class defaults
(mock-walk market data, sqlite DATABASE_URL) with no error (v1 README "Setup"
section; RES009 doc 10). This module loads the repo-root `.env` explicitly,
from a path derived from `__file__` — never CWD — and refuses to run when a
required key is absent rather than degrading silently (CR040 applied to
tooling).

It also absorbs the key-identity trap from v1's README/docstrings: melehost's
Kimi Coding Plan key (`sk-kimi-…`, api.kimi.com/coding) and the Mac's Moonshot
Open Platform key (`sk-…`, api.moonshot.ai) are different products with
different model namespaces; the wrong one was used twice live before being
caught.

This is the ONLY module in library/ allowed to touch `sys.path`
(`ensure_backend_path`) — the bootstrap owns path setup so no other library
module carries a sys.path hack.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = REPO_ROOT / "backend"

VLLM_DEFAULT_MODEL = "ami-llm"

_TRUTHY = {"1", "true", "yes", "on"}


def ensure_backend_path() -> None:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))


def load_repo_env(*, override: bool = False) -> None:
    """Load REPO_ROOT/.env into os.environ explicitly.

    `override=False` matches dotenv's default: real shell exports win over the
    file, so an operator can still shadow a key for one run.
    """
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        raise SystemExit(
            f"{env_path} not found — the repo-root .env is the only env source "
            "this toolkit trusts (backend/.env does not exist and Settings' "
            "env_file resolves against CWD, silently loading nothing)"
        )
    try:
        from dotenv import load_dotenv
    except ImportError:
        _parse_env_file(env_path, override=override)
        return
    load_dotenv(env_path, override=override)


def _parse_env_file(env_path: Path, *, override: bool) -> None:
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = value


def require_keys(*names: str) -> dict[str, str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit(
            f"missing required env keys: {', '.join(missing)} — call "
            "load_repo_env() first, or export them (see "
            "docs/tools/room_investigation/README.md setup section)"
        )
    return {n: os.environ[n] for n in names}


def require_kimi_open_platform_key() -> str:
    key = os.environ.get("KIMI_API_KEY", "")
    if not key:
        raise SystemExit(
            "KIMI_API_KEY not set — needs the Mac's Moonshot OPEN PLATFORM key "
            "(api.moonshot.ai), not melehost's Coding Plan key"
        )
    if key.startswith("sk-kimi-"):
        raise SystemExit(
            "KIMI_API_KEY starts with 'sk-kimi-' — that is melehost's Kimi "
            "CODING PLAN key (api.kimi.com/coding), a different product whose "
            "model namespace does not include kimi-k3. Use the Mac's Moonshot "
            "Open Platform key (sk-…) — this mistake was made twice live "
            "(v1 README / RES009 05)"
        )
    return key


def require_vllm() -> tuple[str, str]:
    """Return (base_url, model) for the on-prem vLLM server.

    Hard-fails only on missing env. The GET /v1/models identity check prints
    the serving model's `root` field (never trust the `ami-llm` alias — D21)
    but only warns on failure: the server may be down at import-check time.
    """
    import httpx

    base_url = os.environ.get("VLLM_BASE_URL", "").rstrip("/")
    if not base_url:
        raise SystemExit(
            "VLLM_BASE_URL not set — export it (e.g. http://192.168.20.74:8000, "
            "LAN-direct from the Mac; unreachable from off-LAN) before running "
            "against vllm"
        )
    model = os.environ.get("VLLM_MODEL", VLLM_DEFAULT_MODEL)
    try:
        resp = httpx.get(f"{base_url}/v1/models", timeout=10.0)
        resp.raise_for_status()
        roots = [m.get("root") for m in resp.json().get("data", [])]
        print(f"vLLM serving model root(s): {roots} (alias requested: {model})")
    except Exception as exc:  # noqa: BLE001 — warn, don't hard-fail on the probe
        print(
            f"WARNING: GET {base_url}/v1/models failed ({exc!r}) — serving "
            "model identity unverified; never trust the alias",
            file=sys.stderr,
        )
    return base_url, model


def require_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit(
            "DATABASE_URL not set — melehost's Postgres via SSH tunnel, e.g. "
            "ssh -f -N -L 5434:127.0.0.1:5434 melehost then export "
            "DATABASE_URL=postgresql+psycopg2://postgres:<pw>@127.0.0.1:5434/ami_trade"
        )
    return url


def require_real_market_data(*, allow_mock: bool) -> None:
    if allow_mock:
        return
    if os.environ.get("USE_REAL_MARKET_DATA", "").strip().lower() not in _TRUTHY:
        raise SystemExit(
            "USE_REAL_MARKET_DATA is not truthy — refusing to run on the "
            "deterministic mock walk (v1's silent-fallback landmine, hit live "
            "2026-09-26). Export USE_REAL_MARKET_DATA=true, or pass "
            "allow_mock=True only for a deliberate mock-data run"
        )
