# AMI Trade Beta: tester onboarding note (WP-52, CR267)

Written 2026-11-19 against `beta/cr267` at `c67aec83`. Menu paths come from `mobile/lib` screens and `app_en.arb` at that commit, including WP-30 (Export my data, Delete account), WP-38 (the `Ref:` line) and WP-21b. **Report this response** and the Room thumbs rating (WP-36) are built on `lane/WP36-beta-settings` and are not merged here, so the note says "coming in the next build"; re-word it when WP-36 lands. Four checks fixed 2026-11-20 (founder rulings, "I fix, you skim"): server location is neutral until gate S4 is decided (marked `<!-- S4 -->`); the privacy link is the live canonical page (v2.1); the experimental label follows the app disclaimer; the support address is `support.ai@agenticmarketintel.ai`, still to confirm. The privacy paragraph follows the BETA DRAFT clauses in `legal/policies/privacy_policy.md` (v2.2, unpublished), so it can say more than the live v2.1 page.

Parts 1 to 3 are for testers. Part 4 is for Saiful only.

---

## 1. Tester note

Word count: 544 (this section, headings included).

### Welcome to the AMI Trade Beta

AMI Trade is a place to practise making and defending trading decisions. You set a mandate (your goals and limits), put tickers to the Room, and see whether a decision holds up. The Room is a simulated desk of AMI analysts who research a ticker, argue it and give a verdict. You can also ask AMI questions, take lessons, and keep a journal of every decision.

### What is simulated

Everything. AMI Trade is an experimental training simulator. It is simulation-only and is not investment advice. No real money moves and no real orders are placed. A Room verdict is the output of a training exercise, checked against your mandate. The Room is experimental: it can be slow, wrong or inconsistent, and we want to hear when it is.

### How to start

1. Open the app. The first screen asks you to tick **I am 18 or older** and tap **CONTINUE**. AMI Trade is for adults only.
2. AMI runs a short interview to set up your mandate. You start as a guest, so no account is needed.
3. To keep your data if you change phone or reinstall, open **YOU** > **SETTINGS** > **ACCOUNT** and tap **SIGN IN**. Use Apple, Google or an email code.

### Report a problem

1. Open **YOU** > **SETTINGS** > **HELP** > **Report a problem**. Pick a category, describe it, add a photo if it helps, and tap **Send report**. Long-pressing the version number at the bottom of Settings opens the same sheet.
2. If an error shows a line like `Ref: 3f9a1c`, tap it to copy the code and paste it into your report. It lets us find the exact failed request.
3. Coming in the next build: **Report this response** on AMI's text, and a thumbs rating after each Room. Until then, use Report a problem and name the ticker.

### Close your account or take your data

In **YOU** > **SETTINGS** > **ACCOUNT**:

1. **Export my data** saves your trades, Room verdicts, mandate, journal and progress as a JSON file.
2. **Delete account** signs you out everywhere. For 30 days you can restore it by signing in again; after that it is permanently deleted.

### What we collect

As a guest, an anonymous ID tied to what you create in the app: chats with AMI, journal entries, Room analyses and simulated trades. If you sign in, we also hold the email and name Apple or Google share and a sign-in identifier; we never see your password. Bug reports carry your text, category, the screen, app version, platform and any photo you attach. We also record device model, OS and app version, crash diagnostics, and basic request data such as your IP address. We do not collect advertising IDs, location, contacts or your photo library. Beta servers are in Asia; the exact location is confirmed before Beta opens. <!-- S4: replace with the chosen host location once gate S4 is decided --> Apple, Google, RevenueCat, Sentry, OneSignal and contracted AI infrastructure providers process data for us only to run the service. We do not sell it or use it for advertising. The full policy is at https://www.agenticmarketintel.ai/privacy/

### Contact

support.ai@agenticmarketintel.ai

---

## 2. TestFlight "What to Test"

Character count: 2004 (limit 4000).

```text
AMI Trade Beta: practise making and defending trading decisions.

AMI Trade is an experimental training simulator. It is simulation-only and is not investment advice. No real money, no real orders. The Room, a simulated desk of AMI analysts, is experimental: it can be slow or wrong, and that is what we want to find out.

PLEASE TRY
1. First run: tick "I am 18 or older", finish the short interview with AMI and set your mandate.
2. Convene a Room on a ticker you know. Read the verdict. Does it fit your mandate? Does the reasoning make sense?
3. Place a simulated trade, then check PORTFOLIO and your Journal (YOU tab).
4. Ask AMI how to do something, for example "How do I report a problem?"
5. Take a lesson or the daily challenge.
6. Sign in (YOU > SETTINGS > ACCOUNT > SIGN IN), then confirm your data is still there after a reinstall.
7. Try Export my data. If you are happy to test it, try Delete account on a spare install, then sign in again within 30 days to restore it.

HOW TO REPORT A PROBLEM
1. YOU > SETTINGS > HELP > Report a problem. Pick a category, describe what happened, add a photo if it helps.
2. If an error shows "Ref: ...", tap it to copy the code and include it. It lets us find the failed request.
3. If this build shows "Report this response" on AMI's text or a thumbs rating after a Room, use them to flag a bad answer. They are the fastest route.
4. Say which ticker and which Room it was.

WHAT WE COLLECT
An anonymous ID tied to your chats, journal, Room analyses and simulated trades. If you sign in, the email and name Apple or Google share. Device model, OS and app version, crash diagnostics and basic request data. No advertising IDs, location or contacts. Not sold, not used for advertising. Delete or export your data any time from YOU > SETTINGS > ACCOUNT. Beta servers are in Asia (exact location confirmed before Beta opens). <!-- S4 --> Full policy: https://www.agenticmarketintel.ai/privacy/

SUPPORT
support.ai@agenticmarketintel.ai

Thank you for testing.
```

---

## 3. Play closed-testing release notes

Character count: 447 (limit 500).

```text
AMI Trade Beta, an experimental training simulator. Practise making and defending trading decisions with a simulated desk of AMI analysts (the Room). Simulation-only: no real money, no real orders, not investment advice.

Try: onboarding, a Room on a ticker you know, a simulated trade, a lesson, sign-in. Report problems from YOU > SETTINGS > HELP > Report a problem, and include any "Ref:" code. Export or delete your data in SETTINGS > ACCOUNT.
```

---

## 4. For Saiful (admin half of WP-52; not for testers)

What "A3" is: `docs/initial_specs/10_delivery/project_plan.md` row A3, "Email provider". Status there: code wired and promoted, but `mail.agenticmarketintel.ai` was still NXDOMAIN, so real delivery was blocked on DNS. The code now prefers Resend (`RESEND_API_KEY`), falls back to SMTP (`SMTP_HOST`), and otherwise logs `email_not_configured_skip` and sends nothing (`backend/app/services/email_service.py`). The support mailbox is the separate item M9 and the outstanding Cloudflare/Resend work in `orchestration/history/lanes/CR049.md` ("BLOCKED" list). The repo already uses `support.ai@agenticmarketintel.ai` on the website footer and as the website API sender (`RESEND_FROM` in `docker-compose.yml`).

Nothing below has been done. Steps, in order:

**A. Choose the address**

1. Confirm the Beta support address is `support.ai@agenticmarketintel.ai`. It is the address the website footer, the support knowledge base and the Resend sender already use, so the note now uses it. If you want a different one, tell Claude and all WP-52 texts get changed together.

**B. Inbound: the mailbox**

1. Cloudflare dashboard > the `agenticmarketintel.ai` zone > Email > Email Routing. Enable it if it is off (it adds MX and an SPF record for you).
2. Create a custom address for the support address above, set the destination to the mailbox you will actually read, and confirm the verification email Cloudflare sends to that destination.
3. If the Beta will be answered by more than you, route to a shared mailbox or group instead of a personal inbox.

**C. Outbound: email DNS (A3)**

1. Look at what exists. From the Mac: `dig +short MX agenticmarketintel.ai`, `dig +short TXT agenticmarketintel.ai`, `dig +short A mail.agenticmarketintel.ai`. Note what is already there before adding anything.
2. Create (or log in to) a Resend account, add the domain `agenticmarketintel.ai` (Domains > Add Domain), and create an API key with sending access.
3. Copy the DNS records Resend shows for that domain into Cloudflare DNS, exactly as displayed: the SPF record, the DKIM record (`resend._domainkey`), and the return-path MX if it lists one. Set each to "DNS only" (grey cloud), not proxied.
4. SPF must stay one single TXT record starting `v=spf1`. If Email Routing already added one, merge the Resend `include:` into it rather than adding a second record; two SPF records make SPF fail.
5. Add a DMARC record: TXT on `_dmarc` with `v=DMARC1; p=none; rua=mailto:<support address>`. Keep `p=none` through the Beta; tighten later.
6. In Resend, click Verify on the domain and wait for status "Verified".
7. Give Claude the API key through your usual secrets route (not in a chat or a commit). Claude sets `RESEND_API_KEY` and `SMTP_FROM` on melehost `.env` (and on the Beta host when it exists), recreates `ami_api_alpha`, and checks the logs show `magic_link_email_sent`. `docker-compose.yml` already forwards both.
8. The `mail.agenticmarketintel.ai` A record from the earlier SMTP route is only needed if you choose SMTP instead of Resend. Skip it if Resend is verified.

**D. Acceptance test: mail delivered both ways**

1. In: from an outside account (not on this domain), send a message to the support address. It must arrive in the destination mailbox, not spam.
2. Out: in the app, sign in with a fresh email address and request the code. The "Your AMI Trade sign-in code" message must arrive in that inbox within a minute, not in spam.
3. In the received message's headers (Gmail: Show original), confirm `SPF: PASS`, `DKIM: PASS`, `DMARC: PASS`.
4. Reply to the incoming test from the support address (or send from Resend's dashboard to an outside inbox) and confirm that arrives too.

**E. Before the note goes to testers**

1. The support address is filled in (see A). Skim it once.
2. Server location: the note says "Beta servers are in Asia; the exact location is confirmed before Beta opens". Gate S4 is open. Once S4 is picked, replace that sentence (search for `<!-- S4`) in the note and the TestFlight text.
3. The note links the live canonical policy, `https://www.agenticmarketintel.ai/privacy/` (v2.1, effective 2026-09-25). The Beta wording (v2.2) is an unpublished draft; publishing it needs counsel and the 14-day notice (clause 16). The link stays the same when v2.2 goes live.
4. TestFlight: App Store Connect > the app > TestFlight > Test Information > "What to Test", paste part 2. Play Console > Testing > Closed testing > the release > Release notes, paste part 3 (if the console asks for language tags, wrap it as `<en-US>` ... `</en-US>`).
5. When WP-36 merges, tell Claude to change "Coming in the next build" to the real labels.
