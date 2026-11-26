# SOLUTION — make Room numbers provenance-linked, not prose-inferred

## Independence

1. I did not read any contributor subfolder.
2. The checked-out `main` did not contain ISS003. I read only the shared
   `ISS003_problem_statement.md` from local commit `6a98972a`, plus the shared protocol.

## Decision

1. The framing is wrong. A label/window matcher over free prose cannot know whether a number
   names the sheet scalar, a statistic derived from a sheet, a mandate value, a trade
   expression, or a prior desk's argument.
2. Remove the inferred matcher from the user-visible path. The next attempt must not add more
   exclusions for the next phrase.
3. Make every user-visible Room number a server-owned **numeric atom** selected by ID. The
   model writes non-numeric prose and atom references; the server renders the atom's label and
   canonical value.
4. A false correction becomes **impossible at the final render boundary**: AMI no longer emits
   "sheet's own figure is Y, not X". A turn with an unprovenanced number is rejected, repaired
   once, then replaced by a visible availability error. Nothing is corrected by inference.

## 1. Concrete contract

1. Build one frozen `RoomFactLedger` before any desk runs. It is the union of:
   1. live numeric leaves in the market-specific fact sheet;
   2. code-computed derived values already used by the Room, such as history means and
      ATR-derived distances;
   3. mandate values, such as the single-name cap;
   4. prior debate atom IDs;
   5. coded trade/risk values, such as ladder outputs.
2. Each atom carries `id`, source path, label, canonical rendered value, market, and the sheet
   state that made it visible.
3. Use the same ledger to render the fact sheet and to offer numeric references to agents.
   There is then no second hand-maintained field-to-label table to drift.
4. Replace free strings that can contain factual numbers with a segment union:
   1. `{"text":"..."}` — prose;
   2. `{"atom":"sheet.fcf_ttm"}` — a value selected by ID.
5. The atom enum is built per call from the ledger IDs available to that desk. The JSON schema
   and the runtime validator both enforce it. This is not a prompt request.
6. `text` segments may not carry a numeric expression. The runtime validator rejects Unicode
   numeric characters and the complete English numeric-word vocabulary (`one ... trillion`,
   ordinals, fractions, dozen, twice, double, triple). Alpha is English-only; AR and MS need
   locale validators before enablement.
7. The server, never the model, renders every atom as an atomic labelled phrase. Example:
   1. model: `["Cash flow remains ", {"atom":"sheet.fcf_ttm"}, "."]`;
   2. output: `Cash flow remains TTM FCF: -RM15,433M.`
8. The output keeps the atom ID, source path, and rendered span in `AgentMessage` telemetry.
   Streaming waits until the complete turn passes this boundary. A character stream cannot
   strand an invalid prefix in the UI.
9. Apply the contract to desk bodies, stance headlines, PM narration and kill criterion, and
   Risk Officer `key_number` / `decisive_number`. Already-typed geometry fields continue to be
   rendered by code.
10. Keep `numeric_quotation.py` only as a shadow logger during one policy revision. It may never
    append, strip, rewrite, null, or demote user text. Its findings are labelled
    `suspected_unpaired_phrase`, not `mismatch`.

## 2. Invalid, fabricated, and altered figures

1. The model cannot supply an altered numeric value because an `atom` part contains only an ID.
2. A raw `RM9,000M`, `14.2x`, `-8.0%`, or rewritten sign in a `text` part is rejected.
3. Unknown and unavailable atom IDs are rejected.
4. After rejection, make one bounded repair call with the structural error code and exact
   rejected part. No prose explanation is placed in Room content.
5. If the retry still fails, publish:
   `AMI could not safely publish this desk's numeric evidence.`
   and retain the structured error in telemetry. This is fail-loud, not silent fallback.
6. CR038 protection is not weakened for direct fabrication or alteration of a registered figure:
   those values cannot reach the wire. It is narrowed to provenance, not semantic interpretation.
   A model can still select a real but irrelevant atom; the canonical label remains visible, so
   the reviewer sees exactly which source it used. That is not a fabricated number.
7. The visible correction channel is gone. A correct desk sentence can no longer be contradicted
   by a heuristic that inferred a wrong field.

## 3. False-correction SLO and population measurement

1. Acceptable false corrections in AMI's voice: **0 per user-visible Room**. One incident is a
   release blocker and promotion rollback condition.
2. The metric is `rooms_with_ami_false_correction / rooms_with_displayed_content`, not one note
   on one ticker. A release audit must contain:
   1. 3,000 US Rooms;
   2. 3,000 Bursa Rooms;
   3. at least 100 distinct symbols per market, spread across sectors and numeric-field
      availability states;
   4. the real model/provider-policy combinations used in the release.
3. Zero events in 3,000 Rooms gives a one-sided 95% upper bound of about 0.10% per market. The
   zero SLO remains stricter than that statistical bound.
4. Run the audit on stored output envelopes, not by merely re-running the old unit fixture:
   resolve every atom against its frozen ledger and re-render the transcript byte-for-byte.
5. Separately report:
   1. `unprovenanced_raw_numeric_rejections`;
   2. `second_attempt_publish_failures`;
   3. `valid_atom_wrong_source_selections` from sampled human review.
6. The third metric is the residual risk and must not be hidden inside a false-correction count.

## 4. Missing fields and off-sheet figures

1. Bursa's smaller sheet creates a smaller ledger. An unavailable US-only or filing-only ID is
   absent from the JSON enum, so the model cannot cite it. There is no nearest-field or
   percentage-versus-amount fallback.
2. A mandate value exists under `mandate.*`; the 1.0% single-name cap is rendered from the
   resolved mandate, never compared with a percentage field from the company sheet.
3. A multiple or derived value must be created in code and registered under `derived.*`:
   1. four-year mean FCF is one atom with source `mean(fcf_history)`;
   2. `1.0x ATR(14), RM0.145` is one code-computed atom with the ATR value and multiplier
      as inputs;
   3. an unsupported new formula has no atom and therefore cannot be stated.
4. A figure first introduced into the debate can be used later only as an alias to an earlier
   atom ID. The later desk cannot retype or recompute it.
5. Dates and list ordinals are either non-factual prose or registered context atoms. The backend
   no longer tries to decide whether `FY2024` or `(1)` is a measurement.

## 5. Verification and production regression detection

1. A reviewer can run the self-contained demo:
   `python3 -B -m unittest discover -s docs/dilemmas/ISS003_ROOM_FACTCHECK_FALSE_CORRECTIONS/MAI_CODE2 -p 'test_*.py'`.
2. The demo proves the implementation boundary:
   1. canonical negative and currency values are server-rendered;
   2. mandate, derived, and prior-debate atoms resolve;
   3. digit, word-number, and Unicode-number raw claims are rejected;
   4. unknown or market-missing atom IDs are rejected;
   5. unseen non-numeric phrasing cannot rewrite the atom;
   6. no `AMI checked ... not X` string is generated.
3. The real-suite minimum is:
   1. every Round 1-3 sentence translated into a payload attempt and pinned to either valid
      atom rendering or structural rejection;
   2. end-to-end SSE test proving no event is sent before a complete turn validates;
   3. bank/replay test proving the frozen ledger, not the current sheet, renders an old Room;
   4. property test varying prose text while holding the atom ID fixed;
   5. mutation test removing one final-boundary check and requiring a red build.
4. Keep a release canary with at least 100 US and 100 Bursa Runs per provider/model policy.
   Canary input includes negative money, `x`, `%`, `M`/`B`, history statistics, mandates,
   absent Bursa fields, and debate quotations.
5. In production, the final serializer records numeric spans twice:
   1. from atom render offsets;
   2. by independently scanning the rendered string for numeric characters and English number
      words.
   Any scanned number outside a recorded atom span is a schema-invariant breach. Do not
   publish; emit a P0 metric and an explicit turn error.
6. Alert or block promotion on:
   1. any displayed `AMI checked` correction note;
   2. any unowned numeric span reaching the final serializer;
   3. any displayed atom whose source no longer equals the frozen ledger;
   4. repair-exhaustion rate above 1% for either market;
   5. repeated registration omissions for one field.

## 6. What this misses

1. It does not prove financial reasoning. A desk can choose a valid sheet atom and use it in a
   misleading sentence. The atomic label exposes the source, but semantic argument validation
   remains a separate problem.
2. It does not prove that the upstream market value is correct. The desk and fact sheet now
   share the same server-owned source; if that source is wrong, they are consistently wrong.
3. A numeric expression encoded in an unrecognised word or future locale can bypass an incomplete
   lexical validator. That is why digits are not the only check, the English vocabulary is
   build-pinned, and AR/MS need their own verified gates before use.
4. A desk loses some linguistic freedom. It must cite an existing atom rather than invent a new
   off-sheet quantity in prose.
5. Fully arbitrary user-language numeric paraphrases cannot be guaranteed without the same
   language gate. The proposal deliberately trades that capability for no false correction.

## 7. Cost

1. New dependencies: none. Reuse Pydantic/JSON schema, Python Unicode categories, and existing
   on-prem vLLM structured output.
2. Model calls: zero added on the valid path. One bounded repair call on contract failure; the
   turn fails visibly after that.
3. Latency: final local validation and rendering should remain under 10 ms per desk turn. The
   acceptance benchmark rejects the implementation if p95 exceeds 20 ms without a model-call
   timeout. That is measurable on the existing unit fixture.
4. Tokens: budget at most 15% output overhead and 1,500 prompt tokens per desk for IDs/schema.
   The schema should contain only that desk's allowed IDs. A higher measured cost is a reason
   to narrow the ledger or change compression, not to return to raw numeric prose.
5. Initial developer effort: about 5-7 engineer-days for the ledger, output schema, Room runner
   integration, replay version, metrics, and tests.
6. Each new sheet field needs one ledger registration: `id`, `label`, `formatter`, and source
   state, plus one value/unit test. Simple scalars should take under 30 minutes; a new compound
   figure with several meanings must define separate atoms rather than reuse an ambiguous ID.

## 8. Failure posture

1. Missing value, stale ledger, unknown atom, formatter failure, repair failure, or validator
   exception fails closed before streaming.
2. The result is visible AMI copy explaining that numeric evidence was not safely publishable,
   plus telemetry. It never silently falls back to the unverified original string.
3. The old inferred matcher cannot degrade the UI because it has no render capability or
   correction call site.
4. A false positive now costs one unavailable desk turn, not a false lesson in AMI's voice. That
   is the acceptable asymmetry for an educational product.

## 9. Why round 4 does not defeat it

1. Round 4 can change wording, punctuation, sign placement, unit spelling, clause boundaries,
   currency, or proximity without changing the validation result.
2. It can only publish a number by referencing a ledger atom. The new phrase is not reparsed to
   infer what field the author meant.
3. Every Round 1-3 fix was a lexical rule added after a counterexample. This control changes the
   representation so the counterexample class cannot enter the publish path at all.

