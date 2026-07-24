<!-- intake stub — direct Saiful ask, filed during a daily check-in session. Architect triages + mints. -->
# ai-support-inbox — proposed CR: M9 customer support to be AI-managed, first-line

PROPOSED-KIND: CR
SOURCE: Saiful (direct) — "We need support to be managed by an AI. update m9 to include an AI
response. Maybe using Hermes or something."
TRIAGE: NEEDS-INFO

**Proposal:** `project_plan.md` M9 ("Customer support inbox + first-line response playbook") is
currently scoped as Saiful-external/manual. Saiful wants the first-line response AI-managed
instead of (or in addition to) a human playbook.

**Distinct from CR049 — do not conflate.** CR049 already shipped an AI FAQ auto-answer, but it's
scoped to the **marketing website's** public contact form (`website_api`, pre-signup visitors,
`faq_answer.py` KB-grounded engine + deterministic escalation pre-filter). M9's "customer support
inbox" reads as the **live product's** support channel — signed-in/anonymous users hitting
`POST /v1/feedback/bug` → `bug_reports` (melehost), triaged today via `/fix-bugs` — a different
surface, different data (account/billing/trade complaints, not general inquiries), different
stakes.

**Naming — "Hermes" not yet defined.** Grepped the repo: no existing system called Hermes.
`hermes_folder/` appears only inside CR080's QA/Appium report path
(`qa/appium/README.md`, `docs/forward_planning/CR080_appium_uat_harness/`) — unrelated, a
report-output directory name, not a support system. Saiful said "maybe" — read as a proposed
codename, not a locked decision. Also touches the standing **AMI naming rule** (CLAUDE.md:
user-facing copy says "AMI," never "the AI," never a second AI persona name) — if this ships
user-visible ("Hermes" in a support-reply signature, etc.) that likely needs to read as AMI to
stay consistent; "Hermes" may only be an internal/dev codename. Needs Saiful's call before build.

**Guardrail note (carry into the CR, don't skip):** per CR038 (prompt instructions ~30%
effective — not a control) and CR068 (ToS already hardened against "the LLM gave bad advice"
claims), an AI-managed support inbox handling real account/billing/complaint content is
higher-stakes than CR049's FAQ bot. Should reuse CR049's structural-escalation-filter pattern
(deterministic pre-filter blocking advice-seeking/legal/account-deletion intents → human), not a
prompt-only "be careful" instruction.

**Open questions for Saiful before minting:**
1. Scope: full AI-managed reply pipeline on `bug_reports`, or just AI-assisted triage/drafting
   with Saiful sending? (Different build size, different risk.)
2. Does "Hermes" need to be user-visible, or is it an internal codename only (user sees "AMI")?
3. Relationship to CR043 (bug-report feedback loop — toast-on-resolve) — CR043 already closes the
   "tell the reporter when it's fixed" loop; this CR would own the "respond automatically" half.

**Owner (suggested):** `coder.api` (bug_reports response automation, reuse `faq_answer.py`
pattern) — content/KB grounding may need a `noncoder.edu`-style lane if it needs a dedicated
support KB distinct from the app's lesson corpus.

---
*Architect: this needs a `Q:`/`A:` round with Saiful before minting — scope + naming both open.
`project_plan.md` M9 already updated in place with a forward pointer to this stub (docs-only,
no CR needed for that edit per the exemption).*
