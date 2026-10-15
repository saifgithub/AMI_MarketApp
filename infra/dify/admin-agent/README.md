# AMI Ops — Dify agent package (CR200-R003)

Repo-home for the conversational admin agent: everything needed to rebuild
the Dify app "AMI Ops" from scratch. The agent talks to the AMI
LLM (on-prem vLLM) and administers the live app through Dify tools that are
thin HTTP wrappers over the existing `/v1/admin/*` surface — glue, never
new business logic (spec: `docs/forward_planning/CR200-R003_admin_agent_console/`).

Plane rule (binding): this agent administers the application. It must never
offer or invoke development-control actions — no promote, rollback,
migration, or deploy anything.

## Deployment

Dedicated stripped Dify stack on melehost (decision 2026-10-15): compose
project `ami-ops-dify`, host dir `/home/saiful/ami-ops-dify/`, Tailscale-only
nginx on `http://100.110.14.31:8081`. Facilities removed: plugin marketplace
(`MARKETPLACE_ENABLED=false`), knowledge crawlers, embed, multi-user surface
(single operator account). The live alpha stack on melehost and the shared
`frontend-dify-*` stack on minihost (prime_radiant) are untouched. Stack
definition + sanitized env: `../ami-ops-stack/`.

## Files

1. `tools-openapi.yaml` — OpenAPI 3 spec for the slice-1 read-only tools.
   Import into Dify as a custom tool (see below).
2. `agent-instructions.md` — the agent's system prompt. Paste into the
   Dify app's instructions field. Carries the house rules: data only from
   tools, preview-confirm before any send, mermaid for concepts never
   data, deep-link for drill-down.

## Rebuild path

1. Dify (melehost, `ami-ops-dify` stack) → Tools → Custom → import
   `tools-openapi.yaml`. Set the tool's auth to **API key / Bearer** with
   the Alpha `ADMIN_SECRET` (from `infra/alpha.env` — never committed).
   Set the server URL to the LAN-direct alpha API `http://192.168.20.59:8001`
   (same posture as `scripts/messages.sh`; override with the `servers` block
   if the port differs).
2. Create an Agent app → model provider: OpenAI-compatible →
   `http://192.168.20.74:8000/v1` (on-prem vLLM), model per the gateway
   preference (vllm first).
3. Paste `agent-instructions.md` into Instructions. Enable the imported
   tools.
4. Smoke-test: "How many signups in the last 30 days?" must return a tool
   call, then either a markdown table or a `![chart](...)` image link that
   renders.

## Slice status

1. Slice 1 (read-only tools + chart endpoint): chart endpoint shipped
   (`GET /v1/admin/chart.svg`, `api/admin_chart.py`, commit `7756a5a2`);
   Dify stack + tool wiring above.
2. Slice 2 (action tools — messages, push, bug triage, user verbs):
   pending. Action tools get an `X-Admin-Operator: dify-agent` header so
   `admin_audit` names the chat operator (small `get_admin` delta, filed
   with slice 2).
