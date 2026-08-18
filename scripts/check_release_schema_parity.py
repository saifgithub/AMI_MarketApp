#!/usr/bin/env python3
"""check_release_schema_parity.py — refuse to ship a client the deployed backend cannot serve.

DEF195. `0.1.0+61` was uploading to TestFlight with a settings screen that PATCHes seven new
Mandate fields while Alpha's live `Mandate` schema contained NONE of them. Had a user opened that
build before the backend promotion, the screen would have loaded, they would have set a post-loss
cooldown, the PATCH would have returned **200**, and Pydantic's `extra='ignore'` would have dropped
every unknown key. A control that looks authoritative and writes nothing is DEF129 exactly — the
defect CR101 exists to abolish — reintroduced not by any code but by DEPLOYMENT ORDER.

It was caught only because the Architect happened to write "nothing promoted yet" into an audit
brief and then checked the claim. There was no gate, no test, no alarm.

THE ASYMMETRY THIS CLOSES
-------------------------
`infra/PROMOTION_HOLD.md` already guards the other direction — backend ready on `main`, client half
not yet on any device — because that case hurt enough to earn a mechanism. The reverse had none,
even though it is the more dangerous of the two: a client ahead of its backend fails *silently with
a success response*, whereas a backend ahead of its client is merely inert.

WHY A SCRIPT AND NOT A CHECKLIST
--------------------------------
"Remember to promote the backend first" is the prompt-instructions-are-not-controls mistake (CR038)
in release form. The rule here is mechanical: derive the keys the client can PATCH, read the live
backend's OpenAPI, and fail on any key the deployed backend would not accept.

    backend promotes FIRST, client ships SECOND.

USAGE
    scripts/check_release_schema_parity.py                      # against Alpha over the LAN
    scripts/check_release_schema_parity.py --base-url https://api-alpha.agenticmarketintel.ai
    scripts/check_release_schema_parity.py --openapi-file /tmp/openapi.json   # offline

Exit 0 = every client PATCH key exists on the deployed backend. Exit 1 = it does not, or the check
could not be performed. **Exit 1 on "could not perform" is deliberate**: a parity gate that passes
when it cannot reach the backend is worse than no gate, because it reports safety it never checked
(CR040). That is the same reasoning as the vacuity leg on this project's other guards.

KNOWN LIMIT, stated rather than discovered later: the client key set is scraped from Dart source,
not from a declared manifest, so a sufficiently novel way of writing the PATCH body could escape it.
The scrape fails loudly if it finds nothing, so the failure mode is a false ALARM, not a false pass.
If the settings screen is ever restructured, this file is the thing to update in the same commit.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DEFAULT_BASE_URL = "http://192.168.20.59:8000"   # melehost over the LAN; the Mac is on it

#: Sent on every fetch. See DEF330 in `load_openapi` — without it Cloudflare
#: refuses the public hostname and the gate cannot check the host it exists to
#: check. Identifies the caller in the edge logs rather than pretending to be a
#: browser.
_USER_AGENT = "ami-release-schema-parity-gate/1.0 (+DEF195)"

# Where the client's PATCH body is actually built. Each entry is (path, regex, what it captures).
# Keep this list next to the code it scrapes — if the settings screen moves, this moves with it.
_CLIENT_SOURCES = [
    (
        "mobile/lib/screens/settings/settings_screen.dart",
        re.compile(r"""updates\[\s*['"]([a-z0-9_]+)['"]\s*\]\s*="""),
        "top-level keys assigned directly into the PATCH body",
    ),
    (
        "mobile/lib/screens/settings/risk_limits_section.dart",
        re.compile(r"""case\s+['"]([a-z0-9_]+)['"]\s*:"""),
        "risk-limit keys, which reach the body via _pendingRiskLimits",
    ),
]

# The nested `compliance` object is sent whole, so its keys are checked against the backend's
# Compliance schema rather than Mandate's.
_COMPLIANCE_SOURCE = (
    "mobile/lib/models/mandate.dart",
    re.compile(r"""^\s*(?:if\s*\([^)]*\)\s*)?['"]([a-z0-9_]+)['"]\s*:""", re.M),
)


def _scrape(path: str, pattern: re.Pattern, *, within: tuple[str, str] | None = None) -> set[str]:
    f = REPO / path
    if not f.is_file():
        die(f"client source not found: {path} — this checker is out of date with the app")
    text = f.read_text(encoding="utf-8")
    if within:
        start, end = within
        i = text.find(start)
        if i == -1:
            die(f"could not locate `{start}` in {path} — the PATCH body was restructured; "
                f"update {Path(__file__).name} in the same commit")
        j = text.find(end, i + len(start))
        text = text[i: j if j != -1 else len(text)]
    return set(pattern.findall(text))


def client_patch_keys() -> tuple[set[str], set[str]]:
    """(top-level Mandate keys, nested compliance keys) the client can send."""
    top: set[str] = set()
    for path, pattern, _why in _CLIENT_SOURCES:
        top |= _scrape(path, pattern)

    comp_path, comp_pattern = _COMPLIANCE_SOURCE
    compliance = _scrape(comp_path, comp_pattern, within=("Map<String, dynamic> toPatchJson()", "}"))

    # Vacuity: an empty scrape must fail, never pass. This is the leg that stops the guard
    # silently becoming a no-op the day someone renames a widget.
    if not top:
        die("scraped ZERO top-level PATCH keys from the client — the scrape is broken, not the app")
    if not compliance:
        die("scraped ZERO compliance PATCH keys from the client — the scrape is broken")
    return top, compliance


def load_openapi(base_url: str | None, openapi_file: str | None) -> dict:
    if openapi_file:
        p = Path(openapi_file)
        if not p.is_file():
            die(f"--openapi-file not found: {openapi_file}")
        return json.loads(p.read_text(encoding="utf-8"))
    url = f"{base_url.rstrip('/')}/openapi.json"
    # DEF330 — an EXPLICIT User-Agent, and it is load-bearing, not politeness.
    # Alpha's public hostname sits behind Cloudflare, which 403s the default
    # `Python-urllib/3.x` UA as a bot. This gate was proven against the LAN
    # default (http://192.168.20.59:8000, no Cloudflare in front of it) and so
    # exited 0; against the ONLY host a store build actually points at
    # (AMI_API_URL_ALPHA = https://api-alpha.agenticmarketintel.ai) it returned
    # 403 on every call and could never have passed. Wiring it in that state
    # would have produced a release gate that fires on every release — which
    # teaches the operator that firing does not mean stop (DEF277, and the same
    # shape as /v1/llm/status in the promotion protocol). Measured 2026-08-18:
    # no UA -> 403, any UA -> 200.
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:      # noqa: S310 — our own host
            if r.status != 200:
                die(f"{url} returned HTTP {r.status} — cannot verify parity, refusing to pass")
            return json.loads(r.read().decode("utf-8"))
    except OSError as e:
        die(f"could not reach {url} ({e}).\n"
            f"  A parity gate that passes when it cannot reach the backend would report safety it "
            f"never checked, so this is a FAILURE, not a skip (CR040).\n"
            f"  From the Mac, melehost is on the LAN at {DEFAULT_BASE_URL}; pass --base-url for "
            f"another environment, or --openapi-file for an offline check.")


def backend_keys(spec: dict) -> tuple[set[str], set[str], str]:
    schemas = spec.get("components", {}).get("schemas", {})
    mandate = schemas.get("Mandate")
    if not mandate:
        die("the deployed OpenAPI has no `Mandate` schema — wrong host, or a backend too old to check")
    version = spec.get("info", {}).get("version", "unknown")
    mandate_props = set(mandate.get("properties", {}).keys())

    compliance = schemas.get("Compliance") or schemas.get("ComplianceFlags") or {}
    return mandate_props, set(compliance.get("properties", {}).keys()), version


def die(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL,
                    help=f"backend to check against (default: {DEFAULT_BASE_URL})")
    ap.add_argument("--openapi-file", help="read a saved openapi.json instead of fetching")
    args = ap.parse_args()

    top, compliance = client_patch_keys()
    spec = load_openapi(args.base_url, args.openapi_file)
    be_mandate, be_compliance, version = backend_keys(spec)

    where = args.openapi_file or args.base_url
    print(f"▶ client PATCH keys: {len(top)} top-level + {len(compliance)} compliance")
    print(f"▶ backend ({where}, v{version}): {len(be_mandate)} Mandate + {len(be_compliance)} Compliance")

    # `compliance` is itself a client key AND a nested object; the backend has it as a property.
    missing_top = sorted(k for k in top if k not in be_mandate)
    missing_comp = sorted(k for k in compliance if be_compliance and k not in be_compliance)

    if not missing_top and not missing_comp:
        print("✓ every key this client can PATCH exists on the deployed backend.")
        return 0

    print("", file=sys.stderr)
    print("✗ RELEASE BLOCKED — this client would send keys the deployed backend does not accept.",
          file=sys.stderr)
    for k in missing_top:
        print(f"    Mandate.{k}      absent from the deployed schema", file=sys.stderr)
    for k in missing_comp:
        print(f"    Compliance.{k}   absent from the deployed schema", file=sys.stderr)
    print("", file=sys.stderr)
    print("  Pydantic's extra='ignore' means those PATCHes return 200 and write NOTHING. The user", file=sys.stderr)
    print("  sets a control, sees it accepted, and nothing happens — DEF129's exact shape, caused", file=sys.stderr)
    print("  by deployment order rather than by any code (DEF195).", file=sys.stderr)
    print("", file=sys.stderr)
    print("  Fix: promote the backend FIRST, then ship the client. /promote-to-alpha, then re-run.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
