---
description: Send a real OneSignal push notification to a specific user's registered device(s), from the Mac, without SSH/docker syntax memorized. Resolves the user by email via the admin API (LAN-direct), shows their devices, confirms before sending, then sends via melehost. CR193.
---

# /send-test-push

Trigger a real push notification against a real account, for confirming push delivery
end-to-end or for testing a specific title/body/deep-link. Built because DEF209 proved every
technical link in the push pipeline (auth, credentials, device registration) but nobody had
ever run the last step — a send observed arriving on a real handset — and that step required
SSH + docker syntax nobody had packaged. See `docs/forward_planning/CR193_push_console/CR193.md`.

**This sends a real, user-visible push.** Always confirm with the operator before step 4.

## What to do, in order

### 1. Get the target email

If the user typed an email after the slash command, use it. Otherwise ask:

> "Which account should I send the test push to? (email)"

### 2. Resolve the user — LAN-direct, no SSH

melehost is on the LAN; hit it directly rather than through the Cloudflare tunnel
(`api-alpha.agenticmarketintel.ai`), per the standing route preference. The admin secret is
already on the Mac at `infra/alpha.env` (`ADMIN_SECRET=...`).

```bash
ADMIN_SECRET=$(grep '^ADMIN_SECRET=' infra/alpha.env | cut -d= -f2)
curl -fsS -H "Authorization: Bearer ${ADMIN_SECRET}" \
    "http://192.168.20.59:8000/v1/admin/users?email=<email>"
```

This returns a list of `AdminUserSummary`. If empty, tell the operator no account matches
that email and stop. If more than one match (shouldn't normally happen — email should be
unique), show them and ask which `user_id` to use.

### 3. Show the account's devices and confirm

```bash
curl -fsS -H "Authorization: Bearer ${ADMIN_SECRET}" \
    "http://192.168.20.59:8000/v1/admin/users/<user_id>"
```

Read `.devices[]` (`device_model`, `os_version`, `app_version`, `last_seen_at`) and show them
to the operator. **Say plainly:** OneSignal targets this whole account (`external_user_id` =
`user_id`) — the push will go to *every* device listed, not one specific phone. If the
operator wants a single-device test, they need an account signed into only that one device.

Ask for (or confirm defaults for) the push content:

- **Title** (default: `"AMI Trade test push"`)
- **Body** (default: `"This is a test — ignore. Sent <date> via /send-test-push."`)
- **Type** (default: `test_push` — free-form, only used for the notification row's `type`
  column, doesn't affect delivery)

Then confirm explicitly:

> "Send '<title>' / '<body>' to <email> (<n> device(s): <models>)? (y/n)"

Do not proceed without an explicit yes.

### 4. Send it

The send only works from inside the `api-alpha` container — no HTTP route triggers `notify()`
today (deliberately out of scope for CR193; see its doc). SSH to melehost and exec in,
following the same pattern as `/promote-to-alpha` / `/rollback-alpha`:

```bash
ssh melehost "cd ~/ami_trade && docker compose exec -T api-alpha \
    python -m scripts.send_notification \
    --user-id <user_id> --title '<title>' --body '<body>' --type <type>"
```

(The container already bind-mounts `./backend/scripts:/app/scripts:ro` — no `docker cp`
needed despite what the script's own docstring says.)

### 5. Report the result

The script prints `notification_id=... push_status=... push_detail=...`. Relay that verbatim,
then translate `push_status`:

- **`sent`** — OneSignal accepted it. Ask the operator to confirm it actually arrived (banner
  or lock screen) on the device(s) named in step 3 — that on-device confirmation is the part
  no automation can verify.
- **`rate_limited`** — `notify()` shares a per-user budget (1/minute, 3/hour) with real
  notifications sent to that account. Say when the limit clears and don't retry immediately.
- **`not_configured`** — OneSignal credentials aren't loaded in this environment; say so
  plainly, don't imply the push went out.
- **`failed`** — surface `push_detail` (the OneSignal error) verbatim; don't guess at the
  cause.
- **`skipped`** / **`duplicate`** — the notification row already exists for that
  `source_ref`/dedupe key (not usually hit here since this command doesn't set `--source-ref`
  by default) — say so.

## What NOT to do

- **Don't send without an explicit confirm.** Step 3's question is not rhetorical.
- **Don't claim delivery you can't see.** `push_status=sent` means OneSignal accepted the
  request, not that the phone buzzed — always ask the operator to confirm on-device.
- **Don't try to target one device of a multi-device account.** OneSignal's model here is
  per-`external_user_id`, not per-device — say that limitation out loud rather than promising
  something the pipeline can't do.
- **Don't build an HTTP route for this.** Deliberately out of scope for CR193 — SSH+exec is
  fine for founder-only, occasional use, and skips designing auth/audit for a route that would
  otherwise let anyone with the admin secret push arbitrary content to any user.
