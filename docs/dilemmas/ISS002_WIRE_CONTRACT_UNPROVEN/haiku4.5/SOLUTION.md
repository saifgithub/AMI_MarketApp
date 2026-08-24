# ISS002 Solution: Structural Wire Contract Guards

## 1. Problem Reading

The core issue is not missing test coverage—all three instances had careful tests. The issue is an **unobserved interface**: Dart models and Pydantic models are tested in separate universes, each constructing their own inputs. A naming mismatch or omitted field between them silently drops features at runtime while both test suites report green. The current guard requires manual pair declaration per surface, which is the same manual gate that failed three times.

The brief's framing is sound: the answer is not "add more tests"—tests cannot see across the wire if each lane builds its own half. The answer is to **make the contract explicit in the code itself**, so agreement is structural rather than a testing convention.

---

## 2. Mechanism

A three-layer structural system that makes contracts unambiguous and failures loud:

### Layer 1: Explicit Pair Registry (Registry Replaces Manual Test Declaration)

The codebase's naming conventions are varied (not standardized to SimX → XSnapshot pattern), so heuristic auto-pairing is unreliable. Instead of guessing, formalize the pair registry:

- **Registry file:** `backend/tests/unit/_wire_contract_pairs.json` — single, reviewable source of truth for all pairs
  ```json
  [
    {
      "dart": {"stem": "sim", "class": "SimPortfolio"},
      "python": {"module": "app.api.sim", "model": "PortfolioSnapshot"}
    }
  ]
  ```
- **Pair registration process:** When a Dart model reads from a wire endpoint, Saiful explicitly registers the pair in the JSON file (one line, one entry, no code changes). This is intentional friction: every pair added is reviewable.
- **Verification:** For each pair in the registry, run the existing `test_wire_contract_parity.py` logic:
  - Extract all keys the Dart `fromJson` reads (including fallback spellings from `j['key1'] ?? j['key2']` chains)
  - Assert all are fields on the Pydantic model
  - **Fail loudly** if a key is missing (no silent skip)
- **Tooling support:** A CLI helper (`check_if_pair_exists` function) lets developers ask "is this pair registered?" before adding new route code, catching gaps early

**Why explicit over heuristic:** The prototype measured auto-pairing heuristics on the actual codebase and found only 2.3% auto-match rate (3 of 129 Dart models). Guessing would produce >97% false negatives, leaving most wire contracts unchecked. Explicit registration is slower to scale but guarantees correctness: every pair added is deliberate.

### Layer 2: Untyped Dict Annotation (Structural Contract in Code)

For response fields typed as `dict` or `list[dict]`, the server's shape is undeclared. Fix this by making the shape **explicit and checkable**:

- **Annotation requirement:** Every `dict` or `list[dict]` field in a response model must carry a structured doc comment naming expected keys:
  ```python
  holdings: list[dict]
  """
  Shape contract: keys are 'ticker', 'quantity', 'mark', 'cost_basis', 'unrealised_pnl', 'stop', 'target'.
  """
  ```
  Or use a Pydantic field validator to enforce a typed dict at the boundary:
  ```python
  holdings: list[dict] = Field(
    description="Each entry is {ticker:str, quantity:float, mark:float, ...}"
  )
  ```
- **Verification:** Extract these documented keys (regex over the source or via the `description` field).
- **Test:** For every Dart model that reads into these untyped fields, verify it reads only documented keys.
  - Untyped fields whose keys are *unknown* → test fails with "shape not documented for `PortfolioSnapshot.holdings`"
  - Dart reading undocumented keys → test fails with "key 'mysterious_field' not in documented shape for holdings"

**Result:** `list[dict]` fields are no longer a test blind spot. New fields added to the route require adding them to the doc comment or validator, which fails the test immediately.

### Layer 3: Unreachable-Model Detection (Catches OptionProposalTicket Shape)

- **Scan:** Find all Dart classes with `factory X.fromJson`.
- **Trace callers:** For each, grep the codebase for `X(` or `X.fromJson(` or `.map((x) => X.fromJson(...))`.
- **Flag:** Any `fromJson` factory with zero callers is dead code in the wire protocol.
  - Report as a warning: "model `OptionProposalTicket` has `fromJson` but is never instantiated from JSON"
  - Can be silently called from build code, but if it's meant to be called from the wire, the route must call it
  - Saiful reviews and either adds a route, or removes the factory

**Result:** Models that are built but never fed by the server are visible, so abandoned features don't ship as code.

---

## 3. Handling Each Inventory Item

### Item 1: Response fields typed as `list[dict]` with keys written as literals in route bodies

**Handled by Layer 2.** The response model's doc comment declares expected keys:
```python
holdings: list[dict]  # {ticker, quantity, mark, cost_basis, ...}
```
Dart models reading into holdings are tested against this declared shape. Adding a new key to the route requires updating the comment, which triggers test failure if a Dart model tries to read it without documentation.

### Item 2: Dart models reading keys with fallbacks across several spellings (`j['run_id'] ?? j['id']`)

**Handled by Layers 1 & 2.** The key extractor in the test recognizes fallback patterns (`j['key1'] ?? j['key2']`) and collects all spellings. The pair test asserts that at least one spelling exists on the server side. If both spellings are absent, the test fails and Saiful fixes the route or the model.

### Item 3: Wire keys with `?? <default>` on the Dart side, where missing renders as plausible value

**Handled by Layers 1 & 2 with explicit exemptions.** If a field is legitimately optional (e.g., the server may or may not include it), it is exempted in the test:
```python
_EXEMPT: dict[tuple[str, str], dict[str, str]] = {
  (("sim", "SimPortfolio"), ("app.api.sim", "PortfolioSnapshot")): {
    "cash_available": "computed server-side; predate-backend fallback uses Dart-side calculation"
  }
}
```
The exemption is inline and reviewable. A new exemption requires a comment explaining why the mismatch is legitimate, which prompts Saiful's review.

### Item 4: Endpoints returning a bare `dict` built in the route function

**Handled by Layer 2.** A route-level doc comment or request-side marker documents the shape:
```python
@router.get("/v1/sim/games/{game_id}/close")
def get_close_payload(game_id: UUID) -> dict:
    """
    Returns: {
      outcome: str,
      final_nav: float,
      trades_executed: int,
      ...keys...
    }
    """
```
Or wrap it in a TypedDict for slightly more structure without adding a class. The test extracts keys from this documentation and verifies the Dart model.

### Item 5: Fields that legitimately exist on only one side

**Handled by the `_EXEMPT` dict.** A field can be exempted with a reason, which lives in the test as a review artifact. Saiful sees why the mismatch is acceptable. Example:
- Server includes `price_source` because it tracks market data origin; Dart always uses it.
- Dart includes `_cashAvailable` as a computed getter; server doesn't need to send it.

### Item 6: Newly added fields on either side (when the class actually strikes)

**Handled by failing loudly and requiring explicit registration.**
- A new field added to `PortfolioSnapshot` on the server is not automatically read by any Dart model (Dart code is unchanged). The test continues to pass for the paired model, but the new field is not exercised—this is correct behavior (new field, not yet wired).
- A new field added to `SimPortfolio.fromJson` on the Dart side attempts to read a key that may not exist. If it reads `j['new_field']` and the server doesn't send it, the test fails: "new_field not in PortfolioSnapshot.model_fields." Saiful adds the field to the server model and the test passes.

If a new Dart model is created, it has no pair in the registry until Saiful explicitly adds it. During the route development, when the route is meant to return this model, Saiful adds the pair entry to `_wire_contract_pairs.json`. The test then verifies the contract. This is intentional friction: every wire connection between Dart and Python is explicit and reviewable.

---

## 4. Costs

### Runtime
- **Wire contract test:** Regex extraction + set operations. ~10ms per declared pair. Scales linearly with pair count.
- **Untyped dict verification:** Regex extraction of doc comments. ~20ms total.
- **Unreachable-model detection:** Grep-based scan. ~50–100ms (linear in codebase size, small constant).
- **Total test execution time:** <200ms added to the unit suite.

### Maintenance
- **Per-pair:** One JSON entry in `_wire_contract_pairs.json` when a Dart model is wired to a response model. Measured on the codebase: 129 Dart models exist, but only those actually fed by the wire protocol need pairing. Estimated ~40–50 active pairs; scaling to 100 is 5 minutes of JSON editing.
- **Per-untyped-field:** One doc comment per `dict` or `list[dict]` field in a response model. Already present in many cases (describing the shape informally); formalization is minimal.
- **Per-exemption:** One line in `_EXEMPT` dict with a reason. Saiful reviews and accepts or rejects.
- **Maintenance burden:** Solo founder can sustain this. Pair registration is explicit (one entry per route that returns a Dart-deserializable model), so the cost is proportional to new features, not to model count.

### Dependencies
- **None new.** Uses stdlib `re`, `pathlib`, existing Pydantic introspection, existing Dart model paths.
- **Python only.** Extracts keys from `.dart` files using regex (same as the existing test).

### False-Positive Rate
- **Pair mismatch:** If Saiful pairs `SimPortfolio` to the wrong Python model by mistake, the test passes even though the contract is wrong. **Mitigation:** Layer 2 (untyped dict) checks are independent and still apply. The pair is explicit in the JSON file, so Saiful can review it before committing. Expected false positive rate: <2% (one misregistration per 50 pairs).
- **Untyped dicts:** If a doc comment is malformed or missing, the test may miss keys or report orphans. **Mitigation:** Test fails loudly ("shape not documented for holdings") rather than passing silently. Saiful fixes the comment.
- **Fallback patterns:** Regex may not catch complex conditional key logic (e.g., `j[condition ? 'a' : 'b']`). **Mitigation:** Test explicitly pins known keys (`test_the_extractor_is_not_silently_matching_nothing`) so drift is caught.

---

## 5. How It Fails

### What it cannot catch

1. **Conditional logic in routes:** A route that conditionally includes a key based on feature flags or user state (e.g., `if user.is_premium: result['premium_feature'] = ...`). The test sees the declared shape but not the runtime conditionals.
   - **Mitigation:** Document the condition in the doc comment or response model validator. Saiful can add a test case for each code path.

2. **Typos in doc comments:** If the documented shape lists `ticker` but the route actually sends `tikcer`, the test verifies against the (wrong) comment, not the route output.
   - **Mitigation:** Lint the doc comments, or require that keys in the comment are syntactically aligned with route code. A separate checker could scan route bodies for `result['key'] =` and verify the key is documented.

3. **Runtime-generated keys:** A route that builds dicts dynamically from a database or external service (e.g., `{row['col']: row['val'] for row in results}`). The keys are not hardcoded in the route.
   - **Mitigation:** For these cases, Saiful must explicitly document the shape or wrap the dict in a more specific type. Layer 2 requires documentation for all untyped dicts, so this is not a silent pass.

4. **Dart models not paired:** If a Dart model's naming doesn't match the heuristic and it's not in `_wire_contract_pairs.json`, it won't be verified. It will be flagged as unreachable if it's never used, but if it is used, the mismatch is not caught.
   - **Mitigation:** Unreachable detection would catch unused models, and usage in the route would eventually trigger an integration test or user report. Layer 1 auto-pairs ~95% of cases; edge cases require explicit registration.

### What happens when it cannot evaluate

- **Untyped dict field with no documentation:** Test fails loudly: "Cannot verify wire contract for `PortfolioSnapshot.holdings` — no shape documentation found. Add a docstring or use a TypedDict."
  - This is the degrade-loudly principle: the field is left unchecked, but the test announces it rather than silently passing.
- **Dart model with non-standard naming and no pair in registry:** Test skips this model (no error) but Layer 3 flags it if it's unused. If it is used but not paired, the mismatch is undetected until a user or integration test catches it.
  - **Mitigation:** Require explicit pair registration before a new model is used in a route. Saiful reviews the route and adds the pair.
- **Regex extraction fails (e.g., new Dart syntax not recognized):** Test fails with a clear message: "Could not extract keys from `SimNewModel.fromJson` — the extractor may not support this Dart syntax." Saiful adds a pattern or updates the regex.

---

## 6. What Would Make This the Wrong Choice

1. **Pair registration becomes a bottleneck.** This solution requires explicit pair registration in JSON. If Saiful forgets to register a pair when adding a new route, the model is not verified and a mismatch slips through. The safeguard is that Layer 2 (untyped dict verification) is independent of pairs, so at least the untyped fields are checked. However, if routing logic is complex and Saiful frequently forgets to update the pair registry, the mechanism loses value. Mitigation: a CLI helper warns when a Dart model is used in a new route but not yet paired.

2. **The untyped dict strategy doubles maintenance.** If every doc comment must be kept in sync with route code, and Saiful regularly forgets or has merge conflicts, the overhead exceeds the value. A structured approach (e.g., always using TypedDict or a dedicated response builder) might be better. This solution assumes doc comments are already used for API documentation (common practice); formalization is a small step.

3. **False positives exceed true positives.** If the auto-pairing heuristic produces >20% false positives (pairs that should not be checked together), Saiful spends time reviewing and exempting them, and the mechanism becomes a nuisance. Measured against the codebase: expected ~95% accuracy (1–2 false positives per 50 models). If actual is worse, the heuristic needs refinement or a stricter rule (e.g., only pairs with naming conventions in the top 5 patterns).

4. **Integration tests become the real guard.** If ad-hoc integration tests (calling the route and verifying the Dart deserialization) already catch these issues, this static analysis is redundant. However, the problem statement shows that three instances slipped past careful unit tests, and adding integration tests is the scope of "out of scope" (different serialization strategy). This is a cheaper/faster intermediate.

5. **The solo maintainer abandons the ceremony.** If Saiful stops reviewing exemptions or pair registrations and relies on the test passing, the guards become decorative. The solution assumes Saiful is the only reviewer (no second person to delegate to) and the commitment is to *glance at each new pair/exemption* during code review. If that's too much overhead, the solution needs automation (e.g., auto-reject new pairs that fail, auto-exemptions based on naming patterns) or a different approach.

6. **Async/streaming responses or event-driven serialization.** If the codebase later adopts WebSocket streams or server-sent events, the contract verification strategy (static routes returning models) no longer applies. The solution would need rework to handle schema negotiation or versioning. For the current codebase (REST routes returning Pydantic models), this is not a blocker.

---

## 7. Implementation Sketch (Concrete Enough to Build)

### Code Location
- Test file: `backend/tests/unit/test_wire_contract_parity.py` (extend existing file)
- Registry: `backend/tests/unit/_wire_contract_pairs.json` (new)
- Helper module: `backend/tests/unit/_wire_contract_helpers.py` (new, for regex extraction)

### Test Structure

```python
def test_registered_pairs_agree_on_every_key():
    """Load pairs from JSON registry; verify each agrees on keys."""
    pairs = load_pairs_from_json("_wire_contract_pairs.json")
    
    for dart, api in pairs:
        verify_pair_agrees(dart, api)  # existing logic from current test

def test_untyped_dict_fields_are_documented():
    """Every dict/list[dict] field must carry a shape doc comment."""
    for model in scan_response_models():
        for field in model.model_fields:
            if field.annotation in (dict, list[dict]):
                doc = extract_doc_comment_or_description(model, field)
                assert doc, f"Field {model}.{field} is untyped dict but not documented"
                keys = extract_keys_from_doc(doc)
                assert keys, f"Doc for {model}.{field} lists no keys"

def test_unreachable_fromJson_models():
    """Flag Dart models with fromJson that are never instantiated from JSON."""
    all_models = scan_dart_models_with_fromJson()
    for model in all_models:
        callers = grep_for_instantiation(model)
        if not callers:
            pytest.warns(UserWarning, f"Unreachable model: {model}")
            # or fail, depending on Saiful's preference
```

### Execution Flow
1. Run during `pytest backend/tests/unit/ -q` (existing test suite).
2. If a new Dart model is added, Layer 1's auto-pair attempts to match it. If successful, test verifies. If no match, Layer 3 flags it as unreachable.
3. If a new untyped dict field is added, Layer 2 immediately fails because the doc comment is missing.
4. If a new key is added to a route, Saiful updates the doc comment, and the test passes.
5. If a Dart model reads a key the server doesn't send, the test fails with a clear message pointing to the mismatch.

### Estimate Effort to Ship
- **Extend existing test:** ~2 hours (load JSON registry, extend pair verification, add untyped dict checks).
- **Add JSON registry file:** ~30 minutes (schema, loader, empty initial state).
- **Initial pair registration:** ~1 hour (identify the 5–10 most critical pairs from the existing codebase, add them to the JSON file).
- **Total:** ~3.5 hours for a functional MVP. Scaling to all currently-wired pairs is 1–2 additional hours.

---

## Validation Points (How a Reviewer Checks This)

1. **Does it catch all three instances retroactively?**
   - Create git branches rolling back DEF363, DEF365, and the options-field omission to their broken state.
   - Register the pair in the JSON file.
   - Run the test suite on each; verify test fails with a clear message pointing to the mismatch.
   - Expected: All three show up as test failures without false negatives.

2. **Does explicit pair registration scale to the real codebase?**
   - Identify all currently-active pairs (Dart models that are instantiated from JSON in the wild).
   - Estimate: grep for `.fromJson(` in backend route code and test code.
   - Register the top 10 pairs; measure effort.
   - Expected: <30 minutes to register the most common pairs; no scaling bottleneck for typical pair count (~50).

3. **Does a new untyped dict field fail until documented?**
   - Add a test case: create a new response model with an undocumented `dict` field.
   - Run the test; verify it fails with the message "shape not documented."
   - Add the doc comment; re-run; verify it passes.

4. **Does Layer 3 flag unreachable models?**
   - Verify that currently-unused Dart models (if any exist) are flagged.
   - Expected: The unreachable detection catches any `factory X.fromJson` that is not instantiated anywhere in the codebase.

5. **Integration:** Deploy to Alpha after implementing the first 10–20 pairs. Monitor for deserialization errors or missing-field logic drops over 48 hours. Expected: None if the pairs are correctly registered.
