# CR248 test install — minihost, 2026-09-30 (AT:K6)

Spike: stand up the first two CR248 personas as Hermes Agent profiles on minihost,
wired to the on-prem vLLM, with scheduled routines firing autonomously. Test only —
no messaging gateway personas, no production scope.

## What was done

1. **Hermes Agent installed/updated on minihost** — v0.21.5 (upstream `f42f579`), via the
   official `curl | bash` installer (pipe-to-shell flagged). Note: the installer said
   "Updating" — a Hermes install **already existed** on minihost with a live profile
   `meem` (Saiful's personal assistant, gateway running, whatsapp/google wired,
   already using `ami-llm` via vLLM). The test reused that install.

2. **Firewall (temporary, CR248)**: minihost ufw defaults to deny-outgoing; added
   `allow out to 192.168.20.74 port 8000 proto tcp` so minihost can reach the on-prem
   vLLM (`ami-llm` = qwen3.8-flash-next-abliterated-nvfp4, OpenAI-compatible,
   no API key). Same pattern as the CR246 temporary rule. Remove when the test ends.

3. **Two persona profiles created** (`hermes profile create`), each with isolated
   config/memory/skills under `~/.hermes/profiles/<name>/`, each pointed at
   `custom:ami-llm` → `http://192.168.20.74:8000/v1` (transport `chat_completions`,
   copied from the existing `meem` provider block):
   - `neteng` — network engineer. SOUL.md: probe `https://api-alpha.agenticmarketintel.ai/v1/health`,
     layered diagnosis (DNS/TLS/HTTP/body), READ-ONLY, escalate to Saiful on 2nd
     consecutive failure. Routine `alpha-health-watch` cron `*/15 * * * *`, `--deliver local --continuity`.
   - `appsupport` — application support. SOUL.md: watch the local `ami-loadtest` docker
     stack (containers, ERROR/WARNING log counts, diff vs last pass), READ-ONLY,
     triage notes only. Routine `loadtest-stack-watch` cron `*/30 * * * *`, `--deliver local --continuity`.
   (Production melehost is NOT reachable from minihost — personas are told so in their
   SOUL.md and must not pretend to inspect it.)

4. **Gateway convergence (side effect — touches live `meem`)**: per-profile gateways are
   refused ("exactly one gateway per host"); the supported path
   `hermes gateway migrate --multiplex` was run. minihost now runs **one** systemd user
   service `hermes-gateway.service` (linger enabled, survives reboot) serving all four
   profiles (default, meem, neteng, appsupport). `meem`'s standalone gateway process was
   folded in; its platforms stayed registered. A brief restart of Saiful's assistant
   gateway occurred during the fold.

5. **Verified end-to-end**:
   - One-shot smoke tests: neteng probed api-alpha for real (200, 0.47s, layered
     timings, body schema check); appsupport ran a real watch pass (3/3 containers up,
     0 errors, classified a false-positive grep hit correctly).
   - Scheduled runs fired autonomously at the next quarter-hour; outputs landed in
     `~/.hermes/profiles/<name>/cron/output/<job>/`. Both seeded their cron notepads
     (`fail_streak`, `last_sig`) for cross-run diffing/escalation on the next pass.

## Findings

1. **Persona = profile + SOUL.md + cron routine.** The whole pattern is
   `hermes profile create` → `hermes config set` (provider/model) → write SOUL.md →
   `hermes -p <name> cron add`. No code, no plugins. The melehost UAT precedent was
   config, not luck.
2. **vLLM works as the only model endpoint** for both interactive and cron runs —
   no API key needed, `chat_completions` transport, model id `ami-llm`.
3. **Cron scheduler lives in the (single, multiplexed) gateway process.** No gateway
   serving a profile = its cron silently does not fire (`hermes -p <p> cron status`
   warns). Standalone-profile shims block multiplex serving — don't use them.
4. **minihost's deny-outgoing ufw is the recurring friction** for anything that talks
   to LAN peers (vLLM, melehost). Each new integration needs an explicit allow-out
   rule or a decision to relax the default.
5. **The notepad (`--continuity`) gives the learning/escalation loop** — consecutive-
   failure escalation and cross-pass diffs are just KV the persona maintains itself.

## Customer support persona (same day, second slice)

1. **Profile `customersupport` created** on minihost — vLLM provider/model (same pattern),
   SOUL.md written (KB-mandatory procedure, WhatsApp voice, simulation-only +
   no-account-actions hard limits, escalation shape), 39 KB articles copied from
   `content/support_kb/` into the profile, whatsapp toolset structurally restricted to
   `[clarify, memory, skills, file, session_search]` — **no terminal/web/shell on the
   customer channel** (config-level, not prompt-level).
2. **Multiplex constraint discovered + fixed:** the Baileys WhatsApp bridge is **shared
   ingress owned by the default profile** — per-profile `WHATSAPP_ENABLED` does nothing
   under multiplex. My earlier `migrate --multiplex` had silently **stopped serving
   whatsapp for `meem`**. Fix: copied meem's Baileys session to the default profile home
   (`~/.hermes/whatsapp/session`), moved `WHATSAPP_*` (incl. allowlist) to the default
   `.env`, set `gateway.multiplex_profiles: true` + `profile_routes` (Saiful's number →
   `meem`) on the default config. Bridge reconnected on the copied session — meem's
   whatsapp restored, no re-pair needed.
3. **Routing model:** one Baileys bridge = one WhatsApp account for the whole host;
   personas are reached via `gateway.profile_routes` (chat_id → profile). A dedicated
   support *number* needs either a second paired account (standalone gateway, second
   SIM) or WhatsApp Business Cloud API (Meta WABA — the ToS-clean route, needs
   provisioning). Until then, "customer support whatsapp" = routed chats on the shared
   number.
4. **Verified:** KB-grounded one-shot — "charged twice" question answered from
   `billing_double_charge_refund.md` (alpha free tier, email-escalation path, no refund
   promises, human-follow-up boundary), WhatsApp-appropriate tone. Live inbound test
   pending: needs a second allowlisted WhatsApp number routed → `customersupport`, then
   a real message from that number.

## meem retired, connections moved to AMI (same day, third slice)

Saiful, 2026-09-30: "we can stop supporting meem. they are history. whatever
connections now belongs to AMI."

1. **Ownership moves:** meem's Google creds (`google_client_secret.json`,
   `google_token.json`) and `GEMINI_API_KEY` copied into the `customersupport`
   profile; the WhatsApp Baileys session stays on the default profile (shared
   ingress) but the line now serves AMI.
2. **Routing re-pointed:** default-profile `profile_routes` now sends
   Saiful's number → `customersupport` (was → `meem`). The owner gets the same
   support treatment as any user.
3. **meem made inert, not deleted:** its `.env` renamed to `.env.retired` (no
   tokens → nothing of it can serve), its one cron job (`MEEM weekly chase -
   TECH`) paused. Memories/sessions left on disk; deletion
   (`hermes profile delete meem`) is Saiful's call when he's sure.
4. **Verified:** gateway restarted, WhatsApp bridge reconnected
   (`status: connected`, session at `~/.hermes/whatsapp/session`), all four AMI
   profiles served by the one multiplexer.

Live test now possible: any allowlisted number messaging the line lands on
`customersupport`. A second test-customer number still needs allowlisting when
provided.

## Group chats (same day, fourth slice)

Saiful wants the persona in selected group chats. Config on the default profile
(whatsapp is shared ingress): `WHATSAPP_GROUP_POLICY=allowlist` +
`WHATSAPP_GROUP_ALLOWED_USERS=120363408342824493@g.us`, route
`ami-group-1` (that group JID) → `customersupport` in `gateway.profile_routes`,
`whatsapp.require_mention: true` (in-group it answers only @mentions / replies to
its messages / `/commands` — flip to `false` for open participation).
Caveat recorded: with `WHATSAPP_ALLOWED_USERS` set, group participants must also be
on the sender allowlist — today only the owner's number is; admitting every group
member requires dropping the sender allowlist (DMs then deny-all/ignore by policy),
a follow-up decision for Saiful.

## Operational notes

- Stop/pause a persona routine: `ssh minihost "hermes -p neteng cron pause alpha-health-watch"`.
- Watch outputs: `~/.hermes/profiles/<name>/cron/output/<job>/` on minihost.
- Gateway service: `systemctl --user status hermes-gateway.service` on minihost.
- Teardown: pause both routines, `sudo ufw delete allow out to 192.168.20.74 port 8000`,
  optionally `hermes profile delete neteng appsupport`.
