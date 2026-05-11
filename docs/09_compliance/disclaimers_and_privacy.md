# Disclaimers & Privacy

Educational-simulation positioning. GDPR, Saudi PDPL, Malaysia PDPA compliance.

## Universal disclaimer

Every Convene the Room verdict, every 1-on-1, every lesson, every briefing carries a footer:

```
─────────────────────────────────────────────────────
Educational simulation. Not investment advice.
Past performance does not indicate future results.
─────────────────────────────────────────────────────
```

Plus a persistent footer on every screen (small, JetBrains Mono caption):

```
AMI TRADE • EDUCATIONAL SIMULATION • NOT ADVICE
```

This disclaimer is non-negotiable. It's the legal firewall that keeps us out of investment-advisory regulation.

## Disclaimer copy (translated for AR + MS)

EN:
> *"AMI Trade is an educational simulation app. All trades are paper-money only. Agent reasoning is for learning purposes, not investment advice. We are not a brokerage, registered investment advisor, or licensed financial advisor. Past performance, including simulated performance, does not indicate future results."*

AR (translation by Saiful's external translator with native legal review):
> *(Arabic version — keep meaning identical)*

MS:
> *"Aplikasi AMI Trade adalah aplikasi simulasi pendidikan. Semua dagangan hanya menggunakan wang kertas..."*

These appear:
- App Store / Play Store / AppGallery descriptions
- Splash screen on first launch (briefly)
- Wallet & Plan screen
- About & Legal screen
- Every Room verdict card
- Every Decision Journal entry
- Marketing landing page

## Terms of Service highlights

(Full ToS drafted by Saiful with legal counsel. The PRD captures the key points.)

| Provision | Detail |
|---|---|
| **No advice** | Explicit disclaimer that the service is educational. We do not provide personalised investment advice. The 12 agents simulate analyst roles for learning; their outputs are not advice. |
| **No fiduciary** | We are not a fiduciary to users. |
| **No execution** | We do not execute real-money trades. We do not route to brokers. |
| **No guarantees** | All outcomes — sim P&L, model accuracy, agent quality — are best-effort with no warranty. |
| **Limitation of liability** | Standard SaaS — liability capped at fees paid in past 12 months. |
| **Arbitration** | Standard for consumer SaaS. Class-action waiver where enforceable. |
| **Governing law** | TBD with counsel — likely Saiful's jurisdiction with carve-outs for AR/MS markets. |
| **Termination** | User can terminate any time via account deletion. We can terminate for ToS violations (e.g., obvious abuse). |

## Privacy Policy highlights

Required to comply with GDPR (EU users), Saudi PDPL 2023, Malaysia PDPA, CCPA.

### What we collect

| Category | Examples | Lawful basis |
|---|---|---|
| **Identity** | Email, phone, federated provider IDs (Apple sub, Google sub, HMS unionid) | Contract + Legitimate interest |
| **Mandate** | Financial goals, risk profile, compliance preferences, target outcomes | Contract (essential for service) |
| **Behavior** | Lessons completed, Rooms run, journal entries | Contract + Legitimate interest (product improvement) |
| **Technical** | Device type, OS version, IP-derived country, app version | Legitimate interest (operation, security) |
| **Payment** | Subscription state, credit balance. Card details handled by Apple/Google/HMS — we don't see them. | Contract |
| **Communication** | Concierge thread, 1-on-1 history, Coach sessions | Contract |

We do **NOT** collect:
- Real-name verification (no KYC needed — we're sim-only)
- Government IDs
- Bank account or credit card numbers (Apple/Google/HMS hold these)
- Real-money portfolio data
- Biometric data
- Children's data (app rated 17+)

### How we use it

| Use | Detail |
|---|---|
| **Personalisation** | Mandate drives every agent's response |
| **Product improvement** | Aggregate usage to inform feature decisions (anonymised) |
| **Marketing** | Email/push notifications (with consent) about new features |
| **Compliance** | Audit logs for sensitive operations (retained 6 years per typical regulation) |

We do **NOT** sell user data. Ever.

### Where data lives

- **Primary region**: GCP `europe-west3` (Frankfurt). EU data residency.
- **Backups**: GCS in same region. Weekly off-platform `pg_dump`.
- **CDN/static assets**: Cloudflare edge nodes globally (no PII transits these).

For Saudi residents specifically:
- PDPL 2023 allows cross-border processing if adequate protections are in place (EU GDPR adequacy serves)
- We disclose data residency in the privacy policy
- If a Saudi regulator requires in-country processing at scale, we'd add a KSA region in Phase 3

### Data subject rights

Every user, regardless of jurisdiction, can:

| Right | How |
|---|---|
| **Access** | Settings → About → Export My Data. Provides JSON of all user data. |
| **Rectification** | Most fields editable in Settings. For un-editable fields, email support. |
| **Erasure** | Settings → About → Delete Account. 30-day completion. |
| **Portability** | Same as Access export — JSON in machine-readable format |
| **Restriction** | Concierge command: "pause my data processing" (Phase 2 — for now, account deletion is the route) |
| **Objection** | Opt out of marketing via Settings; cannot opt out of essential processing |
| **Withdraw consent** | Same as Objection / Deletion |

All requests honored within 30 days. Audit logged.

### Consent

- **Mandatory consent** to ToS and Privacy Policy at account claim (during onboarding step 5). Cannot skip.
- **Optional consents**:
  - Marketing emails (default: opt-in for transactional only)
  - Personalised ads on Floor Pass (ATT prompt on iOS; GDPR consent on EU)
  - Crash reporting (default: opt-in; user can disable in Settings)
  - Analytics (default: opt-in to anonymised analytics; user can disable)

Consents recorded with timestamps in audit log.

### Cookies / web tracking

Phase 2 marketing site: standard cookie banner (Cloudflare's built-in plus a custom widget for granular consent).

Mobile app: no cookies. ATT consent on iOS for advertiser-identifier; Android GDPR consent dialog.

### Children

App is rated 17+ in all stores. We do not knowingly collect data from anyone under 13 (COPPA threshold) or under 16 (some EU). If discovered, we delete promptly.

### Breach notification

| Threshold | Timeline |
|---|---|
| Any confirmed breach | Notify affected users within 72 hours (GDPR requirement) |
| Regulator notification | Within 72 hours if required |
| Public disclosure | If high impact, within reasonable time + remediation plan |

We maintain a breach response runbook (drafted separately, not in PRD).

## Saudi PDPL specifics

| Requirement | How we handle |
|---|---|
| Lawful basis | Consent + contract necessity |
| Data subject rights | Provided via Settings |
| Cross-border data transfer | Disclosed; rely on EU adequacy framework |
| Children's data | Not knowingly collected; 17+ rating |
| Data Protection Officer | Phase 2 — we appoint a contact when user count justifies |

## Malaysia PDPA specifics

Standard data-subject rights. No major regulatory friction at MVP.

## GDPR specifics

| Requirement | How we handle |
|---|---|
| Lawful basis declared | Yes, in Privacy Policy |
| DSAR (Data Subject Access Request) flow | Via Settings + email channel for edge cases |
| Cookie consent (web) | Phase 2 |
| Right to be forgotten | Account deletion flow |
| Data Processing Agreement with sub-processors | We have DPAs with: Supabase, GCP, OpenRouter, Anthropic, OpenAI, Google AI, RevenueCat, OneSignal, Twilio, Resend, Sentry, PostHog, Azure, ElevenLabs |
| DPO | Phase 2 |
| Privacy by design | Anonymous-first onboarding + RLS + minimal collection |

## Audit log

All sensitive actions are recorded in `audit_log` table:

```python
AuditEvent(
    id: uuid,
    user_id: uuid,
    actor: "user" | "system" | "support",
    action: str,  # e.g., "mandate_edit_hard", "account_delete_request", "consent_change"
    metadata: jsonb,
    ip_address: str,
    user_agent: str,
    created_at: datetime,
)
```

Retained 6 years. PII redacted on user deletion (we keep the action record, not the values).

## In-app legal screen content

Settings → About & Legal links to:
- Terms of Service
- Privacy Policy
- Disclaimers (the long-form disclaimer page)
- Open-source notices (`flutter_oss_licenses`)
- DSAR contact email
- Saudi PDPL-specific contact (Phase 2)

## Cross-references

- Store compliance: [`store_compliance.md`](store_compliance.md)
- Ad policy: [`ad_policy.md`](ad_policy.md) and [`docs/06_monetization/ads.md`](../06_monetization/ads.md)
- Auth + data isolation: [`docs/08_tech/auth.md`](../08_tech/auth.md)
