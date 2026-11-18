# Data Deletion Policy — AMI Trade

> **DRAFT — pending lawyer review.** Not legally binding until reviewed and signed off by counsel. This document formalizes content that was already live on the published HTML page — see "Document status" below.

**Version:** 1.0 (alpha)
**Effective:** 23 July 2026
**Contact:** support.ai@agenticmarketintel.ai / privacy@agenticmarketintel.ai
**Published HTML:** `website/ami-trade/sad-to-see-you-go/index.html` → `https://agenticmarketintel.ai/ami-trade/sad-to-see-you-go`
**Publishing process:** see [`VERSIONING.md`](../VERSIONING.md)

---

## Why this page exists

Google Play's Data Safety policy requires apps that support account creation to offer a
public, web-accessible way to request account and data deletion — reachable without installing
the app — for both Android and iOS users. This page, and this document, are that mechanism. It
is cross-referenced from the [Privacy Policy](privacy_policy.md), clause 12.

## 0. Delete in the app (BETA DRAFT, CR276 — not yet reviewed by counsel)

The quickest route is **inside the app: Settings → Delete account**. No email or form.

1. **Immediately:** you are signed out on every device and the account stops working.
2. **For 30 days:** you can restore it by signing in again with the same Apple, Google or email sign-in and choosing Restore. A guest account with no sign-in attached cannot be restored.
3. **On day 30:** the account and its personal data are permanently deleted (section 2). This cannot be undone.

Before you delete, **Settings → Export my data** downloads your trades, Room verdicts, mandate, journal, lesson progress and settings as a JSON file.

The web form and email routes below remain for people who cannot open the app. A request made that way is verified against the email on file and deleted on the same terms.

## 1. How to request deletion

1. **Fill in the form** on the deletion page with the email address on your AMI Trade account,
   and choose *Delete my account and data*.
2. **Or email us** at support.ai@agenticmarketintel.ai from that same email address, with the
   subject "Delete my account".
3. We **verify** the request using the email on file, so please use the address you signed up
   with.
4. We **delete your data within 30 days** and email you to confirm when it's done.

> _Inspired by: standard app-store account-deletion pattern; matches the retention/response-SLA
> commitments already made in the Privacy Policy (clause 12)._

## 2. What gets deleted — and what we keep

We permanently delete everything associated with your account — your profile, chat and
Concierge messages, journal entries, simulated trades, mandate, and settings. The **only** data
we retain is:

- **Your email address** — kept so we have a record that the deletion was requested and
  completed, and to prevent abuse of the deletion process.
- **System logs** — kept for security, fraud prevention, and to meet our legal obligations.

Everything else is erased. Retained email and system logs are held only as long as needed for
those purposes and are never used to rebuild your account.

> **BETA DRAFT (CR276) — replaces the list above once counsel approves and it is published.**
> What the Beta code does at the end of the 30 days (default mode `delete`):
>
> - **Deleted:** your account row (email, name, Apple/Google identifier, handle, device
>   identifiers), mandate, journal, simulated portfolios, positions and trades, Room runs and
>   verdicts, lesson and challenge progress, badges and reputation, watchlist and price alerts,
>   notifications and inbox messages, conversations with analysts, bug reports and their
>   screenshots, and request/device logs. We also ask OneSignal (push) and RevenueCat
>   (subscriptions) to delete the records they hold under your account ID.
> - **Kept, with no way to tell who you are:** a billing record of plan changes for up to seven
>   years for accounting `[LAWYER REVIEW REQUIRED: confirm period]`; model-usage figures with the
>   prompt, reply and your ID removed; an internal deletion record (an anonymous ID, the time and
>   which tables were emptied). **Your email address is not kept**; the line above about keeping
>   it describes the older manual process and no longer applies.
> - **Head-to-head game records** that name you are removed, which also removes them from your
>   opponent's history.
>
> Server logs older than 90 days are removed automatically.
>
> `[LAWYER REVIEW REQUIRED]` The system can alternatively be set to *anonymise* (keep a scrubbed
> account shell and de-identified simulated activity) or *archive* (block sign-in, keep the data).
> Anonymise is available if counsel prefers it. Archive is **off** and cannot be turned on
> without recording counsel's approval; this policy does not provide for it.

## 3. Request form

The live request form (email, request type, optional details, Cloudflare Turnstile bot check)
posts to `POST /data-request` on the website API. Field names and the API contract are defined
by the HTML implementation at `website/ami-trade/sad-to-see-you-go/index.html` — this markdown
document is the policy text, not the form spec; do not change field names here without
coordinating a backend change.

Request types supported: account + data deletion, data access (copy of your data), data
correction, other privacy request.

---

## Contact

**support.ai@agenticmarketintel.ai** (fastest — used by the live form) or
**privacy@agenticmarketintel.ai**

For the rules of using the service itself, see the [Terms of Service](terms_of_service.md). For
how we handle personal information generally, see the [Privacy Policy](privacy_policy.md).

---

## § Version history

- **v1.1 (BETA DRAFT, unpublished)** — adds section 0 (in-app deletion, 30-day restore window, export) and the Beta retention list under section 2, matching [CR276](../../docs/forward_planning/CR276_account_deletion_export/CR276_account_deletion_export.md). Drops the retained-email line for in-app deletions. Not published and not counsel-reviewed; `website/ami-trade/sad-to-see-you-go/` is untouched.
- **v1.0** — effective 23 July 2026. First formal version. Formalizes content that was already
  live on the HTML page (no prior version existed — the page had no version metadata before
  this pass). Filed as [CR068](../../docs/forward_planning/CR068_legal_docs_hardening/CR068_legal_docs_hardening.md).

When a new version is published, the previous version is preserved at
`/ami-trade/sad-to-see-you-go/v<N>/` (website) and `legal/history/data_deletion_policy/`
(markdown source) for audit, per [`VERSIONING.md`](../VERSIONING.md).

---

## Document status

This document did not previously exist as canonical markdown — it is extracted from the live
HTML page at `website/ami-trade/sad-to-see-you-go/index.html`, which was built and deployed
(CR049/CR050) before this project's markdown-source-of-truth convention existed. It must be
reviewed and signed off by counsel before being treated as legally binding, same as the
Terms of Service and Privacy Policy.
