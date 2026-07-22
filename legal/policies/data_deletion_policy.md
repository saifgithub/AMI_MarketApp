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
