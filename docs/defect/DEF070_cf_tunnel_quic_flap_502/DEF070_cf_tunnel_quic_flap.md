# DEF070 — Cloudflare tunnel QUIC connections flap → intermittent 502s

**Source:** prompt (Saiful, on-device during CR047 acceptance test — *"I am getting
error 502 now"*). **Area:** infra / cloudflared. **Round:** AT:R63. **Status:** fixed.

## Symptom

Users intermittently get **HTTP 502** from `https://api-alpha.agenticmarketintel.ai`
while the backend is fully healthy. A direct probe from the Mac (LAN) and even a
public probe often returns 200 — the 502 is transient and correlates with active
app traffic (SSE Room streams + watchlist quote polls).

## Diagnosis

Backend and host are healthy — this is **not** an origin outage:

- Public `/v1/health` → 200; all `ami_*` containers up/healthy; logs show Rooms
  completing normally (vLLM 200s).
- melehost is idle: load `0.13 0.15 0.12` on 4 cores, 10 GiB RAM free, 0 swap. Not
  resource starvation.

The fault is in the **cloudflared → Cloudflare edge** hop. The tunnel ran on the
default **QUIC (UDP)** transport, and `docker logs ami_tunnel` showed all four edge
connections repeatedly dying and reconnecting:

```
ERR failed to accept incoming stream requests error="failed to accept QUIC stream:
    timeout: no recent network activity" connIndex=2 …
ERR Request failed error="Incoming request ended abruptly: context canceled"
    dest=…/v1/sim/quotes?symbols=INTC,RXT,HPQ,DIS,AMD,… (a live user request, dropped)
```

`timeout: no recent network activity` across every edge IP (not one bad node), with
the host idle, is the canonical signature of a **UDP path problem** — melehost's
network drops/throttles the QUIC (UDP) packets to the CF edge (NAT UDP timeout,
packet loss, or MTU). When all connections are mid-reconnect, the CF edge has no
healthy route for an incoming request and returns **502** to the client. The logs
show it as far back as the tunnel's first boot (2026-05-12 20:09) — a longstanding
intermittent condition that only became visible under sustained app traffic.

## Fix

Switch cloudflared from QUIC to **HTTP/2 (TCP)** transport, which sidesteps every
UDP failure mode (TCP retransmits transient loss instead of hard-timing-out):

- `docker-compose.yml` cloudflared service: add
  `TUNNEL_TRANSPORT_PROTOCOL: ${CF_TUNNEL_PROTOCOL:-http2}` (overridable; defaults
  http2). `--no-deps --force-recreate cloudflared` — backend untouched.
- Verified: `Initial protocol http2`, edge connections registered `protocol=http2`,
  **12/12** public health probes 200, multi-symbol quotes 200 in 0.39 s.

No backend change → no code promote. `TUNNEL_TRANSPORT_PROTOCOL` is a cloudflared env
var, not a backend `Settings` field, so `test_config_compose_parity.py` does not apply.

## Follow-up / not done

- **Root UDP path** unchanged — http2 masks it. If QUIC is ever wanted back (marginal
  latency gain), the UDP path to the CF edge must be fixed first (MTU / firewall UDP
  timeout on melehost's uplink). Revert = set `CF_TUNNEL_PROTOCOL=quic`.
- **No guard** — a tunnel-transport flap isn't unit-testable from this repo (external
  network). The operational check already exists: `/promote-to-alpha` step 7 smoke +
  the 502 runbook in `CLAUDE.md`. Not a recurring *code* class, so no failure_patterns
  entry; recorded here.
