# Counsel brief for the Malaysian lawyer: three narrow questions (CR267, 2026-11-20)

Prepared 2026-11-20 for the founder to send to Malaysian counsel. It states facts and questions only. It contains no legal conclusions. Every web source was checked on 2026-11-20. Where a source is a law-firm summary and not the official text, it says so, and counsel should read the official text.

## About AMI Trade (context, 6 lines)

1. AMI Trade is a mobile training simulator for trading decisions. It is simulation-only: no real money, no real orders, no investment advice.
2. The operating company is Malaysia-based. The Beta is a closed external test (TestFlight and Google Play closed testing) of 20 to 200 testers, for 6 to 12 weeks, English only, adults only (an "I am 18 or older" confirmation, no birth date stored).
3. Testers use the app as a guest (anonymous ID) or sign in with Apple, Google or an email code. Data held: account identifiers, simulated trades and portfolios, journal entries, chats with the AI analysts, bug reports, device and request logs.
4. The Beta host is not yet chosen (programme gate S4 is open). Options on the table are a Singapore VPS, Cloudflare, a managed platform, and Alibaba Cloud (`hosting_comparison_2026-11-18.md`, `cloudflare_options_2026-11-19.md`).
5. The Beta privacy wording is a draft awaiting this review: `legal/policies/privacy_policy.md` (v2.2, BETA DRAFT, unpublished). The live policy is v2.1, effective 2026-09-25, at https://www.agenticmarketintel.ai/privacy/.
6. Programme plan: `docs/forward_planning/CR267_beta_programme/CR267_beta_programme.md` (gate S6, section 3a.2).

---

## Question 1. Ling-3.0-flash model licence

**Question.** Is a licence statement in a Hugging Face model card (licence metadata field only, no LICENSE file in the repository) enough for us to rely on for commercial use, or do we need the licensor's written confirmation?

### Facts

1. How we use it. We run `Ling-3.0-flash-Fin-fp4` on our own server as the backup LLM on Alpha (the second model that answers if the primary is down). Source: `docs/forward_planning/CR281_llm_provider_allowlist/CR281_llm_provider_allowlist.md` (`VLLM_FALLBACK_MODEL=ling-3.0-flash-fin-fp4`) and `docs/forward_planning/CR267_beta_programme/progress.md`.
2. Beta's planned backup is `Ling-3.0-flash` (the general model, not the Fin build) served by a third party (DeepInfra), not on our host. Source: CR281 doc, Beta lines. DeepInfra's own terms are a separate matter and are not part of this question.
3. What the model repositories show (Hugging Face, publisher `inclusionAI`). Checked 2026-11-20 through the page, the raw README and the public Hugging Face API:

   | Repository | URL | Licence shown | LICENSE file in repo | Last modified (HF API) |
   |---|---|---|---|---|
   | Ling-3.0-flash | https://huggingface.co/inclusionAI/Ling-3.0-flash | metadata `license: mit` (sidebar: "License: mit") | none (39 files; none with "licen" in the name) | 2026-10-12 |
   | Ling-3.0-flash-Fin | https://huggingface.co/inclusionAI/Ling-3.0-flash-Fin | metadata `license: mit` | none (77 files) | 2026-09-24 |
   | Ling-3.0-flash-Fin-fp4 | https://huggingface.co/inclusionAI/Ling-3.0-flash-Fin-fp4 | metadata `license: mit` | none (76 files) | 2026-09-10 |

4. The README of Ling-3.0-flash opens with the YAML header `license: mit` and `pipeline_tag: text-generation`. It has no licence section, no copyright notice and no statement about commercial use (raw README: https://huggingface.co/inclusionAI/Ling-3.0-flash/raw/main/README.md).
5. The Fin card states it "extends Ling-3.0-flash through continued training on high-quality financial data". Its model tree lists base model `inclusionAI/Ling-3.0-flash`, marked as a fine-tune. Fin-fp4 lists the same base model. The Fin card says its training-content summary "does not replace the model's technical documentation, usage terms, or license", without naming a licence there.
6. The Ling-3.0-flash repository file listing (checked 2026-11-20): `.eval_results`, `.gitattributes`, `README.md`, `chat_template.jinja`, `config.json`, `configuration_bailing_moe_v3.py`, 24 safetensors shards, `model.safetensors.index.json`, `modeling_bailing_moe_v3.py`, `special_tokens_map.json`, `tokenizer.json`, `tokenizer_config.json`. No LICENSE file.
7. Our own evaluation recorded the same gap earlier: `docs/forward_planning/CR240_llm_provider_evaluation/scorecard_2026-11-18.md` (section 1b, "MIT declared in the card metadata; no LICENSE file in the repo"; "Needs the licence check").

### What we do meanwhile

1. Ling is a backup only. The primary model on Alpha is a different model, and the primary on Beta is DeepSeek-V4-Flash (which does ship an MIT licence file, per the same scorecard).
2. External testers on Beta reach Ling only if the primary fails. A fallback verdict is labelled as such in the stream and in the stored record (CR267 section 3a.1).
3. If counsel says written confirmation is needed, the Ling slot can be switched to another model by configuration only (CR281 `LLM_PROVIDER_ALLOWLIST`, no code change).

### What the answer would change

1. "Model-card licence is enough": Ling stays as the backup on Alpha and Beta. We would ask whether to keep a dated copy of the card and the HF API response as our record.
2. "Need the licensor's written confirmation": we write to the publisher and keep Ling off the Beta path until we have it. We would ask what the confirmation must say, and whether it must also cover the Fin fine-tune and the fp4 build, which are separate repositories.
3. "Need an MIT notice with the copyright holder": we ask where that notice must appear, given that none of the repositories names a copyright holder.

---

## Question 2. Archive instead of delete (gate S6)

**Question.** Under Malaysia's PDPA 2010 (as amended by the Personal Data Protection (Amendment) Act 2024), may we keep a closed account's data in an access-locked archive instead of deleting it, and if so for how long and on what basis?

### Facts

1. The founder's decision on 2026-11-18 was: deactivate at once, restorable for 30 days, then a full access-locked archive; the app says "close account", not "delete", until counsel rules (CR267 section 3, item 8). A later ruling the same day amended this (section 3a, item 2): Beta ships in `delete` or `anonymise` mode with the button reading "Delete account", and archive is switched on only if counsel approves. Gate S6 is off the Beta launch path (CR267 section 4, row S6).
2. The code has three post-grace modes, set by `ACCOUNT_ERASURE_MODE` (`backend/app/core/config.py`, `account_erasure_mode`; `backend/app/services/account_erasure.py`):
   1. `delete` (default, what Beta ships): hard-deletes the user row and every row of personal data.
   2. `anonymise`: keeps a scrubbed tombstone user row (no email, provider IDs, device IDs, handle or name) plus de-identified simulated activity (trades, portfolios, Room verdicts, progress). Free-text and device-level data are still deleted.
   3. `archive`: keeps everything; only sign-in stays blocked.
3. Archive is refused at boot and again at run time unless `ACCOUNT_ARCHIVE_COUNSEL_APPROVED=true` is set. The setting is `false` by default, so archive cannot run by accident (`config.py`, validator `_archive_needs_counsel_approval`).
4. The restore window is 30 days (`ACCOUNT_CLOSURE_GRACE_DAYS`, default 30, allowed 1 to 365). The erasure job runs hourly.
5. What Beta keeps after deletion, per the draft policy (`legal/policies/privacy_policy.md`, clause 10, BETA DRAFT, and `docs/forward_planning/CR276_account_deletion_export/CR276_account_deletion_export.md`): a billing record of plan changes (account ID, plan, date, free-text notes removed) for up to seven years for accounting (marked `[LAWYER REVIEW REQUIRED: confirm period]`); model-usage figures (tokens, cost, model name) with prompt, reply and user ID removed; an internal deletion record with an anonymous ID. Request and model logs older than 90 days are removed automatically.
6. The draft policy says it "does not provide for" archive mode (clause 10, last paragraph).
7. Store rules the plan cites for deletion: Apple App Store Guideline 5.1.1(v) and Google Play's account-deletion requirement (CR267 section 6, WP-30, item 1). The plan reads these as requiring removal of the user's personal data. We have not asked counsel to interpret them; they are context for what archive would have to satisfy.
8. The PDPA retention principle, as summarised by law-firm guides (not read from the Act itself): personal data processed for any purpose "shall not be kept longer than is necessary for the fulfilment of that purpose" (section 10). Source: https://chambers.com/practice-guides/guides/data-protection-privacy-2026/malaysia/law-and-practice (checked 2026-11-20). We did not verify whether the 2024 amendments changed section 10, and found no source on how archived or backup copies are treated.

### What we do meanwhile

1. Beta ships in `delete` mode. `archive` stays off.
2. The draft policy and the in-app dialog state what is deleted and what is kept, and for how long. They stay drafts until counsel reviews them.

### What the answer would change

1. "Archive is permitted, on basis X for period Y": we set `ACCOUNT_ARCHIVE_COUNSEL_APPROVED=true` and `ACCOUNT_ERASURE_MODE=archive`, add the retention period and basis to the policy, and change the button wording to "Close account". We would need the exact period and any conditions (for example, whether the user must be told at sign-up or at closure, and whether the user can still ask for erasure of the archive).
2. "Archive is not permitted for this purpose": Beta stays in `delete` (or `anonymise` if counsel prefers it). We drop the archive plan.
3. "Anonymise is acceptable but archive is not": we move to `anonymise` and ask what standard of de-identification counsel expects.
4. Separate sub-question, same answer sheet: is the seven-year period for the billing record acceptable?

---

## Question 3. Cross-border transfer of personal data

**Question.** If the Beta is hosted outside Malaysia (and its processors are outside Malaysia), what must we do to transfer Malaysian users' personal data lawfully under PDPA section 129 as amended, including the Commissioner's 2025 guideline?

### Facts

1. Hosting. No host is chosen (gate S4). The options include Singapore (Hetzner VPS, or managed platforms with a Singapore region), Cloudflare (global edge, region not pinnable for Containers), Google Cloud (Gulf regions) and Alibaba Cloud (Kuala Lumpur and Riyadh listed). Sources: `hosting_comparison_2026-11-18.md`, `cloudflare_options_2026-11-19.md`. The Beta plan's working recommendation is one Singapore VPS (CR267 section 6, Phase 4), not yet confirmed.
2. Draft policy clause 8A says Beta servers will be in Singapore (planned, host not provisioned) and treats this as a transfer outside Malaysia. It says "By using AMI Trade you consent to these transfers", and flags `[LAWYER REVIEW REQUIRED]` on the lawful basis, whether explicit consent is needed in the sign-up flow, and the processor list and locations. The tester note no longer names a location until S4 is decided.
3. Processors named in the draft policy (clause 7 and 8A): Apple, Google, RevenueCat, Sentry, OneSignal and any contracted AI infrastructure provider. On Beta the LLM provider is DeepInfra (CR281 doc). We have not recorded each processor's data location in the repository.
4. Current statute and guideline, checked 2026-11-20:
   1. Section 129 of the PDPA was amended by the Personal Data Protection (Amendment) Act 2024 (Act A1727), replacing the old Minister-approved whitelist. Per secondary sources, the amended section 129 took effect on 1 April 2025 (commencement order gazetted 24 December 2024). We did not find the gazette notice itself. Sources: https://digitalpolicyalert.org/change/10475, https://www.dataprotectionreport.com/2025/01/new-horizons-in-data-protection-malaysias-personal-data-protection-amendment-act-2024/, Act text: https://christopherleeong.com/wp-content/uploads/2024/12/PDPA-Amendment-Act-A1727.pdf.
   2. The PDP Commissioner issued Personal Data Protection Guidelines No. 3/2025, Cross Border Personal Data Transfer, Version 1.0, dated 29 April 2025. Official PDF: https://www.pdp.gov.my/wp-content/uploads/2025/08/GP_CBPDT_EN-1.pdf (we read its text directly).
   3. Per the guideline (paragraph 4): subsection 129(2) allows a transfer if (a) the place has in force a law substantially similar to the Act, or (b) the place ensures an adequate level of protection at least equivalent to the Act. Paragraph 4.2 lists the 129(3) alternatives, including data subject consent (7: a personal data protection notice naming the class of third parties and the purpose, then recorded consent), contract necessity (8), and reasonable precautions and due diligence through binding corporate rules, contractual clauses or certification (12). For 129(2) the guideline describes a transfer impact assessment (TIA), valid for no longer than three years (paragraphs 5.6 and 6.5).
   4. The guideline also covers contracts with third parties and processors (paragraph 15, including a duty that the processor complies with section 9 of the Act) and record keeping of each receiver and each transfer, with evidence of compliance (paragraph 16).
   5. A law-firm summary matches these points: https://www.mayerbrown.com/en/insights/publications/2025/07/from-legislative-reform-to-practical-guidance-key-amendments-to-malaysias-pdpa-and-the-launch-of-cross-border-transfer-guidelines (checked 2026-11-20).
5. We have not performed a TIA, kept a transfer register, or recorded consent for transfers.

### What we do meanwhile

1. Beta opens only after the host is chosen (S4). The tester note says "Beta servers are in Asia; the exact location is confirmed before Beta opens".
2. The draft policy keeps the transfer disclosure and the processor list. No claim that consent has been validly obtained is made anywhere user-facing.
3. We can add an explicit consent step and a transfer register in the app and policy if counsel advises it. Nothing is built for this yet.

### What the answer would change

1. Which hosting option we may pick: if one destination (for example Singapore) is easier to justify under 129(2) than another, S4 is decided accordingly.
2. Whether we need the consent route (a sign-up notice and recorded consent), the contract route, or a TIA, and who must perform and sign it.
3. Whether processors (Apple, Google, RevenueCat, Sentry, OneSignal, DeepInfra) each need a contract clause or a separate assessment, and whether we may rely on their standard terms.
4. Whether the clause 8A sentence "By using AMI Trade you consent" is sufficient, or the consent must be a separate recorded action.

### Secondary: Gulf users (Saudi Arabia PDPL), one line

If Beta testers in Saudi Arabia are enrolled, the Saudi Personal Data Protection Law and SDAIA's Transfer Regulations (amended 1 September 2024) restrict transfers abroad and require a risk assessment (SDAIA guideline, February 2025); we have only law-firm summaries and ask counsel only to say whether a Gulf user in the Beta changes the answer above (https://insightplus.bakermckenzie.com/bm/data-technology/saudi-arabia-updates-data-transfer-regulations-and-introduces-the-first-set-of-standard-contractual-clauses, https://www.clydeco.com/en/insights/2025/03/update-on-saudi-arabia-risk-assessment-guidelines; checked 2026-11-20, primary text not read).

---

## Out of scope for this brief

We are not asking about any of the following. They are the public-release legal backlog (CR267 section 7) and other items that stay with later work: a full counsel review of the legal documents (Terms of Service, Privacy Policy, data deletion policy, cookie and other notices); the licensing position for market data (the yfinance replacement, CR007); payments, subscriptions and free-with-ads, and ads verification (CR225, CR226); the production cloud, managed Postgres and the vendor terms that come with them; independent security review; analytics; Arabic and Malay versions of the legal text; content verification of lessons (CR060); introducing Buy / Hold / Sell actions; the securities-law position of the product (AMI is a training simulator and is not licensed to give investment advice); the third-party grader vendor's terms (Jev) and DeepInfra's terms; EU, UK and US privacy law (GDPR, UK GDPR, CCPA); and Apple and Google store policy interpretation. If any of these should be added to this engagement, the founder will say so.
