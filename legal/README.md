# Legal

The canonical legal documents for AMI Trade — Terms of Service, Privacy Policy, Data
Deletion Policy, and Competition Rules — kept in markdown as the source of truth, with dated
version history. The customer-facing HTML lives under `website/` and is a manual transcription
of the markdown here (no build pipeline; see [`VERSIONING.md`](VERSIONING.md) for the
publish/sync process).

Created 2026-07-23 (AT:legal CR068) by splitting the pre-existing
`docs/initial_specs/09_compliance/` folder: the actual legal documents moved here; the research
and planning material that fed them stayed in `docs/`. `competition_rules.md` was added the same
day (CR064, AT:legal) once ToS v2.0 landed.

## Structure

```
legal/
├── VERSIONING.md          — how to publish, version-bump, and archive these documents
├── policies/               — current, in-force versions (what counsel reviews, what website/ mirrors)
│   ├── terms_of_service.md
│   ├── privacy_policy.md
│   ├── data_deletion_policy.md
│   └── competition_rules.md
└── history/                 — frozen snapshots of superseded versions, one subfolder per document
    ├── terms_of_service/v1.0_2026-05-18.md
    ├── terms_of_service/v2.0_2026-07-23.md
    └── privacy_policy/v1.0_2026-05-18.md
```

## Where things live

| What | Where |
|---|---|
| Canonical markdown (this folder) | `legal/policies/*.md` — what a lawyer reviews |
| Published HTML for customers | `website/{terms,privacy,competition-rules}/index.html`, `website/ami-trade/sad-to-see-you-go/index.html` |
| Archived HTML versions | `website/{terms,privacy,competition-rules}/v\<N\>/index.html` |
| Archived markdown versions | `legal/history/<doc>/v\<N\>_\<date\>.md` |
| Research + peer-policy sourcing that fed these drafts | [`docs/initial_specs/09_compliance/legal_plan_ami_trade.md`](../docs/initial_specs/09_compliance/legal_plan_ami_trade.md), [`legal_samples.md`](../docs/initial_specs/09_compliance/legal_samples.md) |
| App-wide disclaimer copy, GDPR/PDPL/PDPA operational detail | [`docs/initial_specs/09_compliance/disclaimers_and_privacy.md`](../docs/initial_specs/09_compliance/disclaimers_and_privacy.md) |
| App Store / Play Store / AppGallery compliance | [`docs/initial_specs/09_compliance/store_compliance.md`](../docs/initial_specs/09_compliance/store_compliance.md) |
| Ad content policy | [`docs/initial_specs/09_compliance/ad_policy.md`](../docs/initial_specs/09_compliance/ad_policy.md) |

`legal/` is not deployed by `website/deploy_ftp.py` (same as `docs/` — only files under
`website/` go out over FTP). Publishing a change means editing the markdown here, then manually
applying the same change to the HTML under `website/`, per `VERSIONING.md`.

## Status

All three documents are alpha-stage, founder-drafted, and **not yet reviewed by counsel**. Each
document's own `[LAWYER REVIEW REQUIRED]` / `[LAWYER PLACEHOLDER]` tags and "Document status"
section track exactly which clauses still need a real lawyer. Nothing here is legally binding
until that review happens — see each document's own DRAFT banner.
