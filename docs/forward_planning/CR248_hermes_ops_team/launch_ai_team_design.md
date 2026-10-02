# Launch AI team design — AMI Trade launch and beyond

Working doc (2026-10-02, AT:K6). Imagine AMI Trade launches (alpha→public). What AI
ops team do we need running, what upgrades does the current team need, and what must
we research first. Feeds CR248 (personas), CR036 (GTM), CR245 (beta sizing). Not a
CR itself yet — input to those.

## Current roster (live on minihost)

| Persona | Status | Does today |
|---|---|---|
| neteng | live | api-alpha health probe every 15 min, whatsapp ops group (AT:network) |
| appsupport | live | watches local ami-loadtest stack every 30 min |
| customersupport | live | whatsapp line + 2 groups (listen-all), 39-article KB, 12h digest to home group |
| angelia | live | Chief of Staff: Hermes config admin, one group (listen-all), Saiful-only state changes |

## Gap personas for launch (from CR248's six)

1. **System engineer** — melehost patch cadence, backup verification, capacity/disk
   watches, cert/tunnel rotation ownership. This is exactly CR245 §9–§11 territory:
   the *hosting* decision is CR245's, but the *watching role* is this persona.
2. **Marketing** — executes CR036 messaging pillars: campaign calendar, offer
   activation, store-listing (ASO) iteration, launch-week announcement sequencing.
   Currently content-only, no operating function.
3. **Social media** — fully greenfield. Launch shape: content calendar, the
   "repurpose octopus" pattern (one source asset → many formats), community
   responses. Platform choice is a research item (below).

## Launch upgrades for existing personas

4. **neteng → launch grade:** error-rate and p95 latency watch (not just up/down),
   vLLM gateway health (queue depth, token throughput), tunnel-edge checks, alert
   thresholds with escalation to the CoS group. Define "page Saiful" criteria now,
   not during an incident.
5. **appsupport → launch grade:** real bug_reports triage — read access to the alpha
   DB (read-only user on melehost postgres), crash/ANR ingestion, duplicate
   detection, SLA timers, weekly bug-trend section in the digest.
6. **customersupport → launch grade:** email channel (Hermes-native IMAP/SMTP —
   replaces DEF104), app-store review drafting (draft-for-human; Tier 1), feedback
   themes → product loop (feed the digest into launch decisions), AR/MS language
   readiness plan for v1.0.
7. **angelia → launch grade:** formal squad leader (delegation instructions per
   persona — video review Bin 1.1), kanban PM for launch tasks (Bin 1.2), 08:00
   Riyadh morning briefing to the CoS group (Bin 1.5), launch-week "war room" mode
   (hourly digest, all personas report in).

## Research list (before launch — numbered, each lands as config, a CR, or a test)

8. **Hermes native email channel** — test on minihost; decide if it becomes the
   DEF104 replacement (customer support's inbox). *Test.*
9. **Squads/delegation + native kanban prototype** — wire Angelia → personas squad,
   stand up the ops board. *Config + SOUL work on minihost.*
10. **WhatsApp Business Cloud API** — the ToS-clean path as user volume grows; the
    Baileys personal-bridge ban risk scales with traffic. Compare against Telegram
    bot (cheaper, bot-native) as the primary support channel. *CR + Meta provisioning.*
11. **Honcho shared memory evaluation** — answers whether personas should share
    memory (CR248 open Q5). *Test on minihost.*
12. **Per-persona model routing** — depends on beta LLM capacity decisions (CR245).
    *Deferred until endpoints exist.*
13. **Launch watchlist definition** — what the backend actually exposes today
    (structlog, /v1/health, gateway metrics) and what neteng should watch at 100×
    current load. *Audit + config.*
14. **Capacity escalation thresholds** — disk/RAM/DB-connection/trigger-queues
    thresholds at which the system engineer escalates; ties to CR245 §9–§11. *CR245 input.*
15. **Financial-content compliance for marketing/social** — platform ad policies for
    trading-education content, mandatory simulation-only disclaimers, app-store
    rules on financial claims. *Research → governs the two new personas' SOULs.*
16. **App-store review workflow** — API access, draft-for-human pipeline, response
    templates from the KB. *Config + CR036 input.*
17. **Support volume model** — messages/user/month at alpha density → decides
    whether free-response whatsapp scale or Cloud API/Telegram is the real channel.
    *CR245 input.*

## Open decisions (Saiful)

18. Priority order for standing up the three gap personas (system engineer is the
    cheapest — it watches what already exists; social media is the most expensive).
19. Support channel bet for launch: whatsapp (current) vs Telegram bot vs email-first.
20. Whether the launch team work rides CR248 or gets its own CR (recommend: own CR,
    "CR249 launch ops team", minted at next daily review if Saiful agrees).
