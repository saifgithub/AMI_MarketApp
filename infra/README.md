# `infra/` — environment files + deployment artefacts

This directory holds the canonical-per-environment env files and the
non-code artefacts (systemd units, Cloudflare Tunnel runbooks, backup
configs) for each deployment target.

## Per-environment env files — the model

| File | Status | Target host | Promoted by |
|---|---|---|---|
| `infra/alpha.env` | gitignored, populated | melehost | `/promote-to-alpha` |
| `infra/beta.env` | gitignored, stub until B-items land | GCP Cloud Run (Beta) | `/promote-to-beta` |
| `infra/prod.env` | gitignored, stub until M-items land | GCP Cloud Run (Prod) | `/promote-to-prod` |
| `infra/<env>.env.example` | **committed** | — | — |

**Mac is canonical.** Every secret lives in one of these files on Saiful's
Mac. Promotion scripts `scp` the matching file to the target host's
`~/ami_trade/.env`. The host's `.env` is treated as derivative — never
edit it in-place, because the next promotion will overwrite it.

This model exists because of an incident on 2026-05-13: an early
`/promote-to-alpha` run did `rsync --delete` from Mac → melehost without
excluding `.env`, and melehost's populated file got overwritten by the
Mac root checkout's near-empty one. Alpha dropped to `active_provider=mock`
for ~3 minutes until the values were restored from the prose copy in
`CLAUDE.md`. The fix has two layers:

1. **rsync excludes `.env`** (so accidental sync can't wipe again — see
   commit `f46c901`).
2. **Mac holds the canonical copy** (so even if melehost's disk dies or
   the host gets reprovisioned, the secrets are recoverable). This file
   is what lands on the Mac for that purpose.

## How to use

### First-time setup on a fresh Mac

```bash
# Copy the shape, then fill in real values (ask the previous operator
# or pull from the existing target host).
cp infra/alpha.env.example infra/alpha.env
$EDITOR infra/alpha.env

# Same for beta + prod once those environments exist:
cp infra/beta.env.example infra/beta.env
cp infra/prod.env.example infra/prod.env
```

### Recovering from a working target host

If the Mac copy is gone but the target host is still serving:

```bash
scp melehost:~/ami_trade/.env infra/alpha.env
# beta + prod analogous when those hosts exist.
```

### Rotating a key

1. Rotate in the source dashboard (Cloudflare / Anthropic / Supabase / …).
2. Update `infra/<env>.env` on the Mac.
3. Run `/promote-to-<env>` — that ships the new file and recreates the
   container so the new value takes effect.

### Verifying after a promotion

`/promote-to-<env>` includes a post-`scp` grep check to make sure the
key keys survived. Manual check:

```bash
ssh melehost "grep -E '^(VLLM_BASE_URL|VLLM_MODEL|USE_REAL_MARKET_DATA|CF_TUNNEL_TOKEN)' ~/ami_trade/.env | sed 's/=.*/=<set>/'"
```

All four must read `<set>`.

## What's NOT in this directory

- `mobile/` build secrets (signing keys, Apple Connect API keys) — those
  live in `mobile/ios/` / `mobile/android/` and follow the Flutter
  toolchain's conventions.
- `backend/.env` — historical; the backend reads `~/ami_trade/.env` on
  the target host today, not a per-checkout `.env` on the Mac. The Mac
  has zero running services (memory: `feedback_mac_is_pure_editor.md`).
- Cloud-provider secret stores. Beta + Prod will migrate to GCP Secret
  Manager (item B8 in `docs/10_delivery/project_plan.md`); these
  per-environment files are the bridge until then.

## Other contents

- `cloudflared/` — Cloudflare Tunnel connector config + runbook (A7).
- `systemd/` — backend systemd unit + logrotate config (A8).
- `backups/` — nightly Postgres backup timer + restore drill (A9).
- `local/` — local-dev docker-compose helpers (mostly stale post-AT:R11
  Mac-pure-editor pivot).
- `gcp/` — placeholder for Beta-era GCP infra.
- `cloudflare/` — placeholder for Cloudflare-DNS infra (separate from
  the Tunnel runbook).
