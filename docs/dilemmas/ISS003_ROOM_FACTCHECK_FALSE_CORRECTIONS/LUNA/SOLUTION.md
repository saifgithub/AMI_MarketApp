# ISS003 independent proposal — LUNA

I read the full ISS003 problem statement, invite prompt, Dilemma protocol, and the named fact-check implementation/tests in `beta/cr267`. I did not open another ISS003 contributor folder.

## 1. Proposal: separate evidence validation from prose, then render numbers from claims

The matcher’s field association is an inference. Its output must not be phrased as a fact about which figure is correct. Round 1–3 show that more regex rules do not close this class: signs and units were fixed, then statistic periods, unrelated fields, mandate values, and derived values still triggered false findings.

Make numeric claims an explicit, validated part of the Room output contract:

1. A desk returns content blocks plus a claim ledger. Each numeric claim has an ID, normalized value, unit, display form, and a typed source:
   1. `sheet`: stable field ID, exact per-run value, period/basis, and `field_state=live`.
   2. `mandate`: exact field/value from the run's mandate.
   3. `derived`: registered formula ID, operands by claim ID, and output unit. Examples include a multiple of ATR and an average over the cited historical series. Formula execution is deterministic code; no free-form expression evaluation.
   4. `debate`: prior message ID and claim ID. A claim can be repeated from debate only if its original provenance validated; a quote of an unsupported claim does not launder it.
   5. `hypothesis`: a clearly attributed forecast/scenario, never rendered as an observed fact or as a sheet value.
2. A deterministic renderer owns every user-visible number. Number-bearing blocks reference claim IDs; the renderer obtains the value and unit from the validated claim, rather than accepting a second model-authored number. Unconstrained prose blocks cannot contain numeric literals or recognized English number words; reject a block that does. This is a content-contract change, not a prompt instruction.
3. Validate the entire output before streaming or committing it to the transcript/downstream context. Reject an altered value, missing/unavailable source, invalid formula or period, unsupported debate reference, duplicate/unused claim, or unbound numeric token. Allow one repair call naming the structural error. If repair fails, withhold the affected desk turn (or the smallest independently rendered content block if block boundaries are reliable) and show a neutral AMI status: “AMI couldn’t verify a numeric claim in this desk’s response, so it isn’t shown.” Do not repeat the disputed figure or state that the desk is wrong.
4. Apply the same publication boundary to all affected surfaces: desk prose, CIO kill criterion and narration, stance headline, and Risk Officer `key_number` / `decisive_number` plus their headlines. The verdict and option ladder remain subject to their existing structural safety rules. Stream, transcript, stored replay, and later desks must all consume the validated/rendered result.

This **prevents unsupported numeric claims reaching users** and **makes a false correction in AMI’s voice impossible** because this design has no user-facing mismatch correction. It preserves a CR038 control: a wrong numeric value with a claimed source is rejected before publication, and an invented factual number has no allowed source and is rejected. A correct-but-unverifiable claim may also be withheld; the neutral status says only that the system could not verify it.

The interim `ROOM_FACTCHECK_NOTES=log` is useful for gathering findings, but it is not the final protection: Risk Officer strings are currently treated as verified in log mode, and a false negative from the matcher can pass. Keep the no-note setting during implementation, but do not describe log-only as CR038 enforcement. Do not return to `annotate` as a rollout step.

## 2. False-correction rate and population measurement

The accepted false-correction rate for an AMI-authored statement that a desk’s figure is wrong is **0**. The final path emits no such statement. The current deterministic match may remain as offline telemetry during migration, but it cannot be the authority for user-visible claims.

For every release candidate, replay at least 500 distinct US Rooms and 500 Bursa Rooms across tickers, desks, and field-availability profiles. Include all three historical 1155.KL transcripts as regression fixtures, but do not count them as population evidence. Have reviewers label all rendered AMI statuses and a stratified sample of accepted, withheld, and repaired numeric claims against the run’s source objects, without first seeing the validator’s result. Publish by market and pooled:

1. Count of AMI-authored definitive corrections and false definitive corrections. Both must be exactly zero; a correction string or mutation path in any surface fails the release invariant.
2. False-withholding rate: valid claims withheld / all adjudicated valid claims.
3. Escape rate: invalid or altered factual claims published / all adjudicated invalid claims.
4. Repair and neutral-status rates by market, source type, desk, and field availability.

The 500-Room-per-market floor is a release regression check, not a rare-event confidence claim. For rate claims on residual automated decisions, publish exact binomial 95% intervals. If anyone later proposes reintroducing a user-visible definitive correction, require a separately approved study with enough independent examples per market to bound its false-correction rate below 0.01% at 95% confidence (about 30,000 zero-error examples per market); otherwise keep that correction type out of AMI’s voice. US and Bursa pass independently; pooled results cannot conceal a Bursa failure.

Production monitoring should count validated, rejected, repaired, and withheld claims by market/source/desk, with run ID and ticker for joinable sampling. Sample and human-review claims in both markets. Alert on any output-invariant violation or any emitted definitive correction phrase. Add market/ticker to current findings telemetry or join the run ID to persisted run metadata; the present log event has run/agent/surface/field but no direct market/ticker population dimension.

## 3. Fabricated or altered figures (CR038)

1. **Altered sheet figure:** the claim’s stable field, basis, unit, and value are compared to the exact sheet object for this run. A mismatch blocks before stream/transcript and gets one repair. A second failure withholds the block/turn and discloses the omission neutrally. It does not tell the user “sheet says Y, not X.”
2. **Invented factual figure:** no valid source reference means rejection. Prompt instructions such as “quote accurately” are not part of the enforcement argument.
3. **Scenario or forecast:** allowed only as `hypothesis`, attributed to the desk and worded as conditional. It cannot masquerade as a live sheet value.
4. **Risk Officer figure:** require each `key_number` / `decisive_number` to reference a claim, not merely equal any number anywhere in the sheet/ladder. The current `_quotation_check` accepts any corroborating numeric leaf from that broad corpus; it can establish that a number exists, not that it is the right field, unit, statistic, or source.

This is stricter than the existing matcher for the covered classes: altered/unsupported factual figures are withheld rather than annotated. It does not attempt to adjudicate all financial truth; section 6 names the remaining limits.

## 4. US, Bursa, and figures outside the sheet

1. **Fewer Bursa fields:** the validator builds the available `sheet` source set from that run’s sheet and `field_state=live`. An absent Bursa field cannot be cited as a sheet fact. It may be omitted, stated qualitatively, or given another valid source type. No US-only field list is assumed.
2. **Mandate cap:** use the mandate object’s field ID/value. It is not compared against an unrelated sheet percentage.
3. **Multiple of a sheet value:** cite a reviewed deterministic formula and source claim. For “1.0x ATR (RM0.145),” the multiplier is a formula over ATR; the display value is computed from the same claim. The field itself is not the computed output.
4. **Average / historical value:** cite the period-qualified series and a formula such as mean. Do not compare a four-year average to a TTM scalar.
5. **Debate figure:** cite the original claim ID/message. It must already be validated, and the copied value is renderer-supplied. A debate statement with no valid origin remains an unverified proposal, not evidence.

## 5. How a reviewer proves it and catches the next phrasing

The defense against unseen phrasing is that phrasing no longer binds a number to a field. The typed source reference does. Verify this at the real publication boundary with mutation tests and held-out replays:

1. Start from each valid source type and mutate the value, sign, currency, unit, period, basis, field ID, and source ID independently. The output must be blocked before SSE and transcript commit.
2. Cover the reported Round 1–3 strings: negative values, `11.5x`, multi-year average, percentage beside an amount label, FY/Q periods, forward vs trailing, mandate cap, ATR multiple, and a sign after a currency symbol. Add unseen generated paraphrases, spelled-out values, ranges, list markers, multiple values per sentence, and US/Bursa money formats. For prose-only blocks, any numeric literal or recognized number word must be rejected; numbers can appear only through renderer slots.
3. Exercise unavailable fields and missing field state; valid/invalid formulas and unit conversions; a mandate cap; copied and unsupported debate claims; Risk Officer `key_number` and `decisive_number`; CIO kill criterion/narration; stance headline; ordinary desk text; retry and scripted fallback; and every replay/persistence path.
4. Assert at integration level that a blocked numeric block never appears in user events, saved transcript, journal replay, or later desk prompts; a block-boundary failure must not leak a partial stream. Assert no user-facing correction annotation exists in any path.
5. Keep a held-out dataset not used to develop validators, sampled from both markets and labeled by a reviewer. Re-run it for every release and publish the false-withholding and escape counts. Historical regression tests alone are insufficient: all three earlier rounds passed a narrow set and failed on new forms.

This should use existing Python/schema/runtime tooling; no third-party dependency is justified for numeric reference validation. Run unit tests for individual source types and an end-to-end `RoomRunner` test for the publication boundary. The reviewer can check the renderer and source equality directly; no unverifiable claim about an LLM verifier is required.

## 6. What this misses

1. **Wrong upstream source:** a correctly referenced value can still be wrong because the provider, market adapter, currency conversion, period, or sheet builder is wrong. Provenance is not truth; the source pipeline needs its own quality checks.
2. **Meaning and context errors:** the correct number can be attached to the wrong company, period, unit, or sentence meaning if claim IDs are assigned incorrectly upstream or the renderer binds the wrong claim slot.
3. **Non-numeric falsehoods:** causal, comparative, and qualitative claims remain outside this control.
4. **Number words and future locales:** an English prose guard can miss a novel way of spelling a quantity. Before Arabic or Malay numeric prose is allowed, define and test its number-word handling; otherwise keep numeric content in rendered structured blocks for those locales too.
5. **Hypotheses:** users may still mistake an explicitly attributed scenario for fact. Attribution wording reduces this risk but does not prove the reader understood it.
6. **Availability/UX cost:** a correct figure with ambiguous or unsupported provenance is withheld. The neutral status may occur often at first and can reduce useful Room detail; monitor this separately from fabricated-claim escape.

## 7. Cost and failure posture

1. **Latency/model calls:** add a structured claims channel to existing desk calls. No second verifier call on success. Permit at most one repair call per invalid output; it runs through the configured Alpha gateway, with no Anthropic-specific path and no external dependency. Failed repair adds up to one existing desk-call latency, then content is withheld.
2. **Runtime:** validation is deterministic and linear in claim count. The heavier cost is output tokens, schema/rendering work, and review of omissions.
3. **Effort per sheet field:** add a stable field ID, unit, period/basis metadata, per-market source mapping/availability, and tests for correct value, altered value, and absent field. No prose-label regex needs adding. If it participates in arithmetic, add a reviewed formula and unit tests. A new Bursa field follows the same work only when Bursa actually supplies it.
4. **Migration cost:** all Room outputs and downstream/replay surfaces must use validated blocks. This is a substantial CR; partial application would leave a path for altered numbers to reach users.
5. **Control failure:** fail loudly at the user boundary. If source lookup, validation, or rendering fails, block the numeric-bearing content and show the neutral AMI status; log a structured error and alert. Never treat a checker exception or missing sheet as a pass. Do not label an uncertain number false.

## Scope boundary

Keep `ROOM_FACTCHECK_NOTES=log` during evidence collection. Retire the `annotate` mode and all output mutations based on `_FIELD_SPECS` / broad numeric corroboration when the structural claim path is complete. The current matcher may remain offline as a diagnostic signal with no user-facing authority. The cutover is done only when altered claims fail before every publication surface and no corrective note is emitted.
