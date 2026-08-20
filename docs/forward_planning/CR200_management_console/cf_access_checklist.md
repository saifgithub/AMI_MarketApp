# CR200 — Cloudflare Access setup (Saiful's manual steps)

The backend side is already live: once the two env keys below are filled,
`get_admin` verifies CF Access JWTs and audit rows carry your email. Until
then everything keeps working on the ADMIN_SECRET bearer.

## Phase A — protect the console page (`/admin` only)

1. **Cloudflare Zero Trust dashboard** → Access → Applications → **Add an
   application** → *Self-hosted*.
   - Name: `AMI Admin Console`
   - Domain: `api-alpha.agenticmarketintel.ai`, path: `/admin`
   - ⚠️ Path is `/admin` ONLY. Do **not** cover `/v1/*` — the mobile app
     lives there and would be blocked at the edge.
2. **Policy "Founder"**: action *Allow* → Include → Emails:
   `saiful.mazli@gmail.com`. Login method: One-time PIN is fine (add Google
   as an IdP later if you prefer). Session duration: 24h.
3. **Service token for agents**: Access → Service Auth → Create token, name
   `claude-agents`. Save the Client ID + Client Secret it prints (shown
   once). Add a second policy on the application: action *Service Auth* →
   Include → Service Token → `claude-agents`.
4. **Wire the backend**: on the application's Overview tab copy the
   **Application Audience (AUD) tag**, then in `infra/alpha.env` set:
   ```
   CF_ACCESS_TEAM_DOMAIN=https://<your-team>.cloudflareaccess.com
   CF_ACCESS_AUD=<the AUD tag>
   ```
   (Team domain: Zero Trust → Settings → Custom Pages shows
   `<team>.cloudflareaccess.com`.) Then re-promote, or restart api-alpha
   after shipping the env.
5. **Verify**: incognito `https://api-alpha.agenticmarketintel.ai/admin` →
   CF login page → PIN → console loads with no token prompt. `admin_audit`
   rows from your session now show your email.

## Phase B — later, deliberate: protect `/v1/admin` too

Only after agent scripts send `CF-Access-Client-Id` / `CF-Access-Client-Secret`
headers (otherwise CF blocks bearer-only scripts at the edge before the
backend's fallback can help). LAN-direct access (`http://192.168.20.59:8000`)
bypasses CF and keeps working on the bearer throughout — the CR193
send-test-push path is unaffected.

## Beta / Prod

Same application config pointed at the future Cloud Run hostname — the
backend verifier only cares about team domain + AUD, not the host.
