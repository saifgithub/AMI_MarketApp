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

3. **meem disabled 2026-10-02** (Saiful: "disable the profile meem"): cron paused,
   profile directory moved to `~/.hermes/profiles.disabled-meem/` — out of the served
   set (multiplexer dropped it on rescan), data preserved, reversible by moving it
   back. Its connections had already been migrated (whatsapp session → default
   profile, google creds + GEMINI key → customersupport, angelia cloned from it).

## Angelia — Chief of Staff persona (2026-10-02)

Saiful: duplicate of `meem`, named **Angelia**, with terminal access and capability to
change the Hermes config; responds to exactly ONE whatsapp group, "AMI-Chief Of Staff".

1. `hermes profile create angelia --clone-from meem` — cloned config (ami-llm),
   SOUL.md replaced (Chief of Staff: runs the machine room, config admin for the
   persona fleet, executive register), meem's full skill library carried over.
2. New `hermes-admin` skill: config.yaml/.env/profile/routes/cron management on
   minihost, with the deferred-restart rule (never restart synchronously from own
   turn), no-secrets-into-chat, no-weakening-persona-safety-limits, and an
   admin_changelog.md audit line per change.
3. Whatsapp toolset (cloned from meem): clarify, connections, memory, skills,
   terminal — terminal on whatsapp is the point for this persona.
   **Tightened 2026-10-02:** Angelia's SOUL restricts state-changing actions (config
   changes, restarts) to explicit requests from Saiful's number in the group; everyone
   else gets read-only answers. Sender admission correction (same day): the *bridge*
   forwards every group participant, but the *gateway authz* enforces
   `WHATSAPP_ALLOWED_USERS` on group senders too — Siti Ahmad (966508163452) was
   dropped as "Unauthorized user" until added to the allowlist. Group membership is
   NOT the only gate.
4. Routing: done 2026-10-02 — "AMI-Chief Of Staff" = `120363412619576892@g.us`,
   routed `chief-of-staff` → angelia. No DM route, no other groups.
5. **Wiring as of 2026-10-02:** 5 groups seen — "Hermès AI" → customersupport
   (listen-all), "AT:network" → neteng, "AmiTrade Volunteer User Group" →
   customersupport (listen-all), "AMI-Chief of Staff" → angelia (listen-all —
   added to `WHATSAPP_FREE_RESPONSE_CHATS`; SOUL updated), "Siti saiful ahmed
   Muneeb" (family) unwired. DM → customersupport.
   `/sethome` verified per-profile (source: `slash_commands.py` → per-profile home
   channel + env); only customersupport has a home set (Hermès AI group).

## CS group listen-all + 12h digest to home group (same day, ninth slice — the refined intent)

Saiful's actual requirement: customer support listens to ALL messages in the customer
support group, takes notes, and sends HIM a summary every 12 hours in the home group.
Supersedes the open-ingress experiment (reverted: allowlist groups, allow-all removed,
catch-all route dropped).

1. **Listen-all:** `WHATSAPP_FREE_RESPONSE_CHATS=120363408342824493@g.us` — verified in
   source (`whatsapp_common.py:258`): per-group exemption from require_mention, so every
   message in that group becomes a customersupport turn. (Considered and rejected:
   modifying vendored `bridge.js` for silent capture — `hermes update` would
   conflict/overwrite; bridge `/messages` queue is drained by the gateway, no parallel
   read path; messageStore is poll/quote-internal, not a history feed.)
2. **Notes:** SOUL instructs a one-line-per-message append to `group_notes.md`. Prompt-level,
   not structural — the only honest capture point available without forking vendored code.
   Degradation is visible (bad notes = bad digest).
3. **Digest:** `cs-group-digest` cron `0 6,18 * * *` (06:00/18:00 UTC = 09:00/21:00
   Riyadh) on customersupport — reads the notes, produces a fixed 5-section digest
   (topics / questions+answers / complaints / human action items / verbatim bug
   quotes), archives them into the continuity notepad, truncates the notes file,
   `[SILENT]` on empty windows. Delivered to the home group
   `whatsapp:120363430641676589@g.us` (**assumption: home group = the neteng-ops
   group** — one-line change if wrong).
4. **Verified end-to-end with seeded test notes:** digest delivered to the home group
   (bridge `fromMe` appends to …6589), correct 5-section shape, KB-grounded
   classification, notes truncated after consumption, run completed clean.

Open caveats: other CS-group participants may still hit the sender allowlist (only
the owner's number is on `WHATSAPP_ALLOWED_USERS`) — their numbers surface in
bridge.log `allowlist_mismatch` events with `senderAltId`; add as they appear. Every
CS-group message now costs one vLLM turn (prompt + short reply) — fine at alpha scale.

## Open group ingress (same day, eighth slice)

Direction from Saiful: receive from all groups and any DM, with rules deciding which
persona responds. Findings:

1. **Groups flipped to `WHATSAPP_GROUP_POLICY=open`** (deferred restart): any group
   the bot is added to is live immediately; persona assignment still via
   `profile_routes` (wa-route / neteng self-service). Allowlist mode retained as a
   one-flag fallback.
2. **Content-based routing is NOT native**: `profile_routes` matches identity
   (chat_id/user_id) only; unrouted chats fall to the default profile and stick
   (per-chat sessions). A "which persona answers, decided by the message" engine
   needs a routing plugin on the gateway hook surface — candidate follow-up CR;
   must verify the exact pre-dispatch hook API in v0.21.5 before committing.
3. **Open DMs held**: `WHATSAPP_ALLOW_ALL_USERS=true` would let any stranger talk to
   the AMI line (token cost/abuse; persona toolsets are safe). Product-level call —
   not flipped without Saiful's explicit go.

## Self-service: neteng manages its own group routing (same day, seventh slice)

Saiful: group routing "should be done by the network engineer". Delivered:

1. Verified in source (`gateway/run.py`): `profile_routes` and the whatsapp group
   allowlist are read at gateway/bridge start — `reconcile_served_profiles` reloads
   the served set only, not config. **A gateway restart is unavoidable** for now.
2. So the restart is *deferred*: neteng replies first, then
   `nohup bash -c 'sleep 20; systemctl --user restart hermes-gateway' &` fires.
   Mechanism verified (bridge reconnects, service active).
3. `wa-route` skill installed on the neteng profile (`skills/wa-route/SKILL.md`):
   the `ami-wa-route` commands, the deferred-restart rule (never restart
   synchronously from your own turn), and boundaries (neteng routes only; DM
   allowlist and other personas' routes are owner-only).
4. neteng SOUL.md extended: it owns its group plumbing, uses wa-route itself.
5. Smoke test (one-shot, `-s wa-route`): listed routing state correctly, identified
   its own group, offered to route the still-unconnected group — and **found a real
   bug**: `ami-wa-route` failed under the agent's terminal env (its python3 lacks
   yaml). Fixed: shebang pinned to `/usr/bin/python3`.

Live test for Saiful: message in a new group, then in neteng-ops say
"@neteng add that group to your channel" — neteng should JID-hunt, route, defer the
restart, and confirm.

## Group routing tool (same day, sixth slice)

Manual per-group wiring (JID from log, two config edits, restart) was flagged as
cumbersome — replaced with `~/bin/ami-wa-route` on minihost: `list` shows seen
groups + routes; `add <jid|latest> <profile> [name]` allowlists, routes, restarts,
and verifies bridge reconnection; `remove <jid>` reverses. Idempotent, yaml-safe.
One observed caveat: profile_routes hot-reload on gateway rescan is unproven (no
log evidence), so the tool restarts the gateway (~10s whatsapp reconnect).

## Network engineer's ops group (same day, fifth slice)

New group `120363430641676589@g.us` allowlisted (`WHATSAPP_GROUP_ALLOWED_USERS` now
holds both groups) and routed `neteng-ops` → `neteng`. neteng SOUL.md extended for
group presence: mention-gated, terse group replies, group requests treated like owner
requests for *checks* but infrastructure changes remain Saiful-only direct — even in
the group, it produces commands for humans to run, never runs them. Note: neteng keeps
its terminal toolset on whatsapp (diagnostics are its job) — acceptable for a private
ops group; revisit before any wider membership.

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
