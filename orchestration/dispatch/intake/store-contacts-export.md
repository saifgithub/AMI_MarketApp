<!-- intake stub — requester built + filed the spec folder; Architect transcribes the register row (CR081). -->
# store-contacts-export — proposed CR: tester/user contact export for engagement comms

PROPOSED-KIND: CR
SUGGESTED-ID: CR082
SOURCE: Saiful (direct) — "communicate with them via e-mail or via WhatsApp to keep them engaged"
TRIAGE: OPEN
STATUS: built + verified this session (AT:R64), tagged `(AT:R64 CR082)`

**Proposal:** One re-pullable contact list across TestFlight + app DB for tester engagement.
Spec + acceptance in `docs/forward_planning/CR082_tester_contact_export/CR082_tester_contact_export.md`.

**Shipped (all verified live against alpha DB + App Store Connect):**
- `scripts/users.sh --contacts` — CSV of email-having real users (standing synthetic/seed exclusion applied).
- `scripts/testflight_testers.py` — App Store Connect `/v1/betaTesters` (reuses build_testflight.sh key; fails loud on missing `.p8`).
- `scripts/contacts_export.sh` — merge + dedupe on email, `source` tag; output `contacts_*.csv` gitignored (personal data).

**Findings worth the register/Saiful knowing:**
- **Android not scriptable:** Play API `edits.testers` exposes Google Groups only, not email-list testers. Doc recommends switching the internal track to a Google Group (Saiful's call) to close it.
- **No WhatsApp source:** no phone numbers in either store or `User`; WhatsApp can't be populated by this.
- Contactable = 5 (claimed w/ email) of 65 real users — anonymous-first gap, surfaced by the tool.

**Owner:** coder.store (self-filed). No sub-lanes.

---
*Architect: mint/confirm the id (CR082 free at file time) and write the `cr_list.md` row; status `in_progress`
(open item: Android→Google-Group switch is Saiful-external). Requester did not edit the register.*
