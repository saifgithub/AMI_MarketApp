# Versioning legal documents — Terms, Privacy, Data Deletion Policy

How AMI publishes, archives, and versions its legal documents. Follow this every time `terms_of_service.md`, `privacy_policy.md`, or `data_deletion_policy.md` changes in a way that affects the published copy at `agenticmarketintel.ai/terms/`, `/privacy/`, or `/ami-trade/sad-to-see-you-go/`.

> **Moved 2026-07-23 (AT:legal CR068).** This file, and the canonical markdown it governs, used
> to live under `docs/initial_specs/09_compliance/`. They now live in this top-level `legal/`
> folder. `docs/initial_specs/09_compliance/` keeps the research/planning material that fed the
> drafts (`legal_plan_ami_trade.md`, `legal_samples.md`) plus operational references
> (`disclaimers_and_privacy.md`, `store_compliance.md`, `ad_policy.md`) — see its
> [`README.md`](../docs/initial_specs/09_compliance/README.md).

---

## TL;DR

| What | Where |
|---|---|
| Canonical source markdown | `legal/policies/{terms_of_service,privacy_policy,data_deletion_policy}.md` |
| Archived source markdown | `legal/history/{terms_of_service,privacy_policy,data_deletion_policy}/v<N>_<date>.md` |
| Published HTML — current version | `website/{privacy,terms}/index.html`, `website/ami-trade/sad-to-see-you-go/index.html` |
| Published HTML — archived versions | `website/{privacy,terms}/v<N>/index.html`, `website/ami-trade/sad-to-see-you-go/v<N>/index.html` |
| Machine-readable version + date | `<meta name="document-version">` and `<meta name="document-effective-date">` at the top of each HTML page |
| Visible in the doc | "Version X · Effective DD Month YYYY" in the header; "Version history" section at the bottom |

---

## Version numbering

Use **semantic versioning** for legal docs:

| Bump | Meaning | Examples |
|---|---|---|
| **Major** (1.0 → 2.0) | Material change — counsel-reviewed update, new clauses, changed retention, new data sharing, jurisdiction change, etc. Triggers the 14-day user-notice rule in Privacy §16 / ToS §14. | Adding a new third-party data processor; lawyer-rewrites; changing governing law; tightening or loosening the liability cap |
| **Minor** (1.0 → 1.1) | Non-material clarification — re-wording for readability, fixed cross-reference, expanded example, added contact route. Does **not** require user notice but should still be reflected in the version. | Splitting one clause into two for clarity; adding the Beta App's email domain to the contact line |
| **Patch** (1.0 → 1.0.1) | Editorial — typo, broken link, dead anchor. No user notice. | Spelling, grammar, fixing a `<href>` |

The version in the HTML must match the version in the markdown source. Bump both in the same commit.

---

## Material vs non-material — the gate

A change is **material** if it could reasonably affect the user's decision to use the service or to share their data. Use these tests:

- Does it **expand** what data we collect, what we share, or with whom?
- Does it **shorten** any user right (deletion window, response SLA, retention)?
- Does it **introduce** a new third-party processor or AI vendor?
- Does it **narrow** the user's ability to dispute or terminate?
- Does it **change** the governing law, arbitration clause, or liability cap?

If yes to any → **material → major bump → 14-day notice required.**

If the change is clarification of intent without expanding/narrowing the user's position → minor or patch, no notice required.

When in doubt, treat as material and notify. The cost of an extra in-app banner is low; the cost of an undisclosed material change is high.

---

## Publishing checklist (each version)

1. **Edit the markdown source** in `legal/policies/{privacy_policy,terms_of_service,data_deletion_policy}.md`. This stays the canonical text and is what counsel reviews.
2. **Apply the changes to the HTML** at `website/{privacy,terms}/index.html` (or `website/ami-trade/sad-to-see-you-go/index.html`).
3. **If this is a major bump**, snapshot the **previous** markdown version into `legal/history/<doc>/v<N>_<date>.md`, then archive the **previous** HTML version before saving:
   ```bash
   PREV=1                  # the version being replaced
   cd "/Volumes/Extreme Pro/AMI_MarketApp/website/privacy"
   mkdir -p "v${PREV}"
   git mv index.html "v${PREV}/index.html"       # or cp if you prefer to keep the working file
   # then write the new index.html as the v2 version
   ```
   Update the archived file's `<link rel="canonical">` to point at `/privacy/v1/` (or whatever version it now is) so search engines don't index two pages with the same canonical.
4. **Update the four version markers** in the new HTML:
   - `<meta name="document-version" content="X.Y">`
   - `<meta name="document-effective-date" content="YYYY-MM-DD">`
   - The visible header line ("Version X · Effective DD Month YYYY")
   - Append a new entry to the "Version history" section at the bottom with what changed and why
5. **Update the markdown** with the new version + effective date in its header.
6. **Update the sitemap** (`website/sitemap.xml`) — bump `<lastmod>` on the affected URL, add the archived URL with `priority: 0.1`.
7. **Commit** with message `docs(legal): publish privacy v<N> / terms v<N>`.
8. **Push live**:
   ```bash
   cd "/Volumes/Extreme Pro/AMI_MarketApp/website"
   python3 deploy_ftp.py YOUR_FTP_PASSWORD
   ```
9. **For a major bump**, also trigger the 14-day in-app notice path (see "App-side acceptance tracking" below — Beta+ work).
10. **Smoke-check** the live URL: `curl -s -o /dev/null -w "%{http_code}\n" https://www.agenticmarketintel.ai/privacy/` should return `200`. Check the archived URL similarly.

---

## URL convention

| URL | What it serves |
|---|---|
| `/privacy/` | Current version (always). Stable URL — App Store, in-app links, footer links all point here. |
| `/privacy/v1/` | Permanently frozen v1.0.x family (any patch versions roll up here). |
| `/privacy/v2/` | Permanently frozen v2.0.x family (created when v3 publishes). |
| `/terms/` and `/terms/v<N>/` | Same pattern. |
| `/ami-trade/sad-to-see-you-go/` and `/ami-trade/sad-to-see-you-go/v<N>/` | Same pattern, once this page has a superseded version to archive (currently v1.0, no archive yet). |

Each archived version's HTML must set `<link rel="canonical">` to **itself** (the versioned URL), not to `/privacy/`. This is the difference between "this is what's in force today" (canonical = `/privacy/`) and "this is what v1 said for the record" (canonical = `/privacy/v1/`).

---

## App-side acceptance tracking (Beta+ work)

Once we leave alpha, we'll want backend support for:

- A `policy_acceptances` table recording (user_id, doc, version, accepted_at)
- On every API call, comparing the user's last-accepted version against the current published version
- On a material change, blocking app actions until the user accepts the new version (banner → tap → accept → write row)

This is **not** in scope for the alpha. The alpha policy contains the "we'll notify you with 14 days' notice" clause as a soft promise; the hard enforcement comes when we have the DB plumbing.

Spec for this lives in `docs/initial_specs/10_delivery/project_plan.md` under the Beta items.

---

## What NEVER happens

- Editing a published archived version (`/privacy/v1/`) after it's been live. If you find a bug in an archived version, bump the **current** version with a patch note explaining the correction; archive history is read-only.
- Changing the `effective-date` of an already-published version. The date in the archive is what was in force on that date.
- Renaming or moving the current URL (`/privacy/`, `/terms/`). External integrations, App Store metadata, and Google indexing all anchor here.
- Publishing a major change without the 14-day in-app notice once we're past alpha.
