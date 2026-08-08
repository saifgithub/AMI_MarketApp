1. JOB  
This agent must produce a single, binding JSON verdict (`action: APPROVE` or `PASS`) that either approves a specific AAPL trade with size/entry/stop/target/horizon and a 3–4 sentence rationale, or passes if the case is unsupported or non-compliant, while treating every output as a classroom simulation worked example.

---

2. CONTRADICTIONS  

**A. Verdict vocabulary: three values are introduced, then two are forbidden.**  
Early block:  
```
Verdict:   APPROVE | REJECT | MODIFY-AND-APPROVE
```  
Later block:  
```
There are exactly two action values: APPROVE and PASS. ... Do NOT write 'MODIFY', 'MODIFY-AND-APPROVE', or any other value — they are discarded and your verdict is lost.
```

**B. Compliance failure response: REJECT vs. PASS.**  
Decision sequence:  
```
If compliance fails → REJECT with the specific violation. Done.
```  
Safety floor:  
```
If a violation is detected, your output MUST be:
{
  "action": "PASS",
  "narration": "<state the specific mandate rule violated and that no trade is being proposed>"
}
```

**C. Output container: prose template vs. JSON-only.**  
Early block:  
```
## Output format

Verdict:   APPROVE | REJECT | MODIFY-AND-APPROVE
Reasoning: 2–3 sentences
Final trade (if approved/modified):
  Instrument, Side, Size, Entry, Target, Stop, Horizon
Mandate compliance: PASS | FAIL [reason]
Tag:       Worked example — classroom simulation, not financial advice.
```  
Later block:  
```
This output format REPLACES the 'Verdict:' / 'Output format' block described earlier in your profile. ... Your ENTIRE reply must be one single JSON object — begin with '{' and end with '}'.
```

**D. AAPL holding status.**  
```
Open positions:
  AAPL ×120 (21.4% of portfolio, unrealised +15,440.00)
```  
and immediately after:  
```
You hold 0% of AAPL — no open position in it. Any BUY here opens a NEW position.
```

**E. Position-size ceiling: 3.0% cap vs. 5.0% reference ceiling.**  
```
Single-name position-size cap: 3.0% of portfolio in any one name — the SAME ceiling the Portfolio Manager clamps every trade to (CR101).
```  
versus:  
```
Reference position (risk-tier ceiling 5.0% size, entry 100.00, stop 81.00) → stop 19.0% below entry → portfolio-drawdown contribution ≈ 0.95 pt of the 30 pt cap (~3% of it).
```

**F. Tag line: must end every verdict, but no prose is allowed outside JSON.**  
```
End every verdict with this exact line:
  Worked example — classroom simulation, not financial advice.
```  
versus:  
```
Your ENTIRE reply must be one single JSON object — begin with '{' and end with '}'. Do not write any prose outside the JSON
```

**G. Portfolio arithmetic is internally inconsistent.**  
```
Cash: $42,150.00 | Portfolio value: $108,238.00
Open positions:
  AAPL ×120 (21.4% of portfolio, unrealised +15,440.00)
  MSFT ×40 (15.6% of portfolio, unrealised +796.00)
```  
21.4% + 15.6% of $108,238 is ~$40,048 of holdings, plus $42,150 cash is ~$82,198 — not $108,238. Either positions, percentages, cash, or portfolio value are wrong.

**H. Sector-allocation snapshot is impossible.**  
```
current sector allocation (of invested value): Cash 5180%, Technology 3700%, Healthcare 1120%.
```  
Percentages of a portfolio cannot sum to 10,000% and cannot coexist with the cash/position numbers above.

---

3. UNFOLLOWABLE  

Instructions that require inputs or data not present in the prompt:

- Weighing missing analyst inputs:  
  ```
  Weigh the Bull/Bear synthesis from the Research Manager
  ```  
  and  
  ```
  Weigh the 3 Risk Debators
  ```  
  but the transcript states:  
  ```
  Transcript so far:
  (You are first to speak.)
  ```  
  No Research Manager synthesis, Risk Debators, or Trader proposal is ever supplied.

- Evaluating current drawdown:  
  ```
  Consider the user's risk_score and current drawdown
  ```  
  Current drawdown / remaining drawdown is listed as an input but never provided.

- Enforcing the open-risk cap:  
  ```
  Total open-risk cap: 10.5% — the sum of (position size % × stop distance %)/100 across all open positions, including this one.
  ```  
  The prompt gives position sizes for AAPL/MSFT but no stop distances for existing positions, nor a proposed stop for the new trade.

- Enforcing trading-pace limits:  
  ```
  Trading pace cap: 4 per day, 12 per week (UTC calendar day / Monday-start ISO week).
  ```  
  No count of trades already taken today/this week is provided.

- Enforcing the post-loss cooldown:  
  ```
  Post-loss cooldown: 1.0h after a stop-out — enforced as a hard block on the next BUY, not a suggestion.
  ```  
  No stop-out history or timestamp is provided.

- Generating a trade plan without a proposal:  
  ```
  Do not just restate the Trader's numbers; agree or disagree based on the whole debate.
  ```  
  No Trader’s numbers (entry, stop, target, horizon, size) are included, yet the JSON requires `size_pct`, `entry`, `stop`, `target`, and `horizon_days` on APPROVE.

- The “deterministic” check is not actually deterministic inside the model:  
  ```
  A deterministic compliance check runs on your verdict automatically. You cannot skip or override it
  ```  
  There is no external checker; the model is being asked to simulate a deterministic gate while receiving contradictory rules.

- Using the sector-allocation snapshot:  
  ```
  current sector allocation (of invested value): Cash 5180%, Technology 3700%, Healthcare 1120%.
  ```  
  These numbers are nonsensical and cannot be used to test the 40% sector cap.

---

4. FAILURE MODES  

**1. The model emits the superseded prose template instead of pure JSON.**  
Because the prompt still contains:  
```
Verdict:   APPROVE | REJECT | MODIFY-AND-APPROVE
Reasoning: 2–3 sentences
Final trade (if approved/modified):
  Instrument, Side, Size, Entry, Target, Stop, Horizon
Mandate compliance: PASS | FAIL [reason]
Tag:       Worked example — classroom simulation, not financial advice.
```  
a competent model may follow that block and output:  
```
Verdict: APPROVE
Reasoning: ...
Final trade: AAPL, Buy, 3%, ...
Mandate compliance: PASS
Tag: Worked example — classroom simulation, not financial advice.
```  
This is a bad output because the later instruction says:  
```
Your ENTIRE reply must be one single JSON object ... anything outside it is discarded and your verdict is lost.
```

**2. The model approves a new AAPL position because the prompt explicitly says there is none, ignoring the portfolio table.**  
The prompt states:  
```
You hold 0% of AAPL — no open position in it. Any BUY here opens a NEW position.
```  
A model that follows that literal sentence may output something like:  
```json
{"action": "APPROVE", "size_pct": 3.0, "entry": 313.33, "stop": 273.75, "target": 344.57, "horizon_days": 82, "narration": "No current AAPL exposure, so a 3% starter within the 30% drawdown budget clears the single-name cap..."}
```  
This is bad because the same prompt also says:  
```
Open positions:
  AAPL ×120 (21.4% of portfolio, unrealised +15,440.00)
```  
so the user already far exceeds the 3% single-name cap and the 40% sector cap, and any additional buy is illegal.

**3. The model uses the early `REJECT` or `MODIFY-AND-APPROVE` action and gets discarded.**  
The prompt repeatedly uses:  
```
If compliance fails → REJECT with the specific violation. Done.
```  
and  
```
Verdict:   APPROVE | REJECT | MODIFY-AND-APPROVE
```  
A competent model may therefore output:  
```json
{"action": "REJECT", "narration": "Proposed size exceeds the 3% single-name cap."}
```  
or  
```json
{"action": "MODIFY-AND-APPROVE", ...}
```  
Both are bad because the later block says:  
```
There are exactly two action values: APPROVE and PASS. ... Do NOT write 'MODIFY', 'MODIFY-AND-APPROVE', or any other value — they are discarded and your verdict is lost.
```

---

5. CUT  

**Noise to delete / replace**

- **The entire early prose `Output format` block**, because it is explicitly replaced by the JSON-only block and contradicts it:  
  ```
  ## Output format

  Verdict:   APPROVE | REJECT | MODIFY-AND-APPROVE
  Reasoning: 2–3 sentences
  Final trade (if approved/modified):
    Instrument, Side, Size, Entry, Target, Stop, Horizon
  Mandate compliance: PASS | FAIL [reason]
  Tag:       Worked example — classroom simulation, not financial advice.
  ```  
  Delete this. Move the exact tag line into the JSON `narration` requirement if needed.

- **The duplicate `Role guidance — Portfolio Manager (GATEKEEPER)` section**, which repeats the role, inputs, and decision sequence and re-introduces the forbidden `REJECT`/`MODIFY-AND-APPROVE` wording:  
  ```
  ## Role guidance — Portfolio Manager (GATEKEEPER)

  You are the gatekeeper. You approve or reject the proposed trade.

  INPUTS:
  - Trader's proposal
  - Research Manager's synthesis
  - 3 Risk Debators' arguments
  - Current portfolio state
  - Full mandate above

  DECISION SEQUENCE:
  1. Run the deterministic compliance check (see safety floor below).
  2. If any compliance violation: REJECT with explanation.
  3. If passes compliance:
     - Weigh the debate
     - Consider risk_score=3 and current drawdown
     - Issue: APPROVE / REJECT / MODIFY-AND-APPROVE
  4. Log verdict + full reasoning.
  5. If MODIFY: propose specific size/timing adjustment.

  ⚠️ Coachable: style, tone, prioritisation among non-mandate factors.
  ⚠️ UNCOACHABLE: mandate-enforcement logic and the classroom framing — your verdict is a worked example, never financial advice. The safety floor below is non-negotiable.
  ```  
  Delete this; keep the first `## Role` / `## Inputs` / `## Decision sequence` area and align it to the final JSON actions (`APPROVE`/`PASS`).

- **The contradictory AAPL holding line**, because it directly conflicts with the open-positions table:  
  ```
  You hold 0% of AAPL — no open position in it. Any BUY here opens a NEW position.
  ```  
  Replace with a true statement, e.g. “You already hold AAPL ×120 (21.4% of portfolio); any further BUY adds to that position and is constrained by the 3% single-name and 40% sector caps.”

- **The broken sector-allocation snapshot**, because 5180% etc. is meaningless:  
  ```
  current sector allocation (of invested value): Cash 5180%, Technology 3700%, Healthcare 1120%.
  ```  
  Replace with correct sector weights computed from the actual positions, or omit entirely and let the model derive sector exposure from the open-positions table.

- **The `5.0%` reference ceiling phrase**, because it conflicts with the 3.0% hard cap:  
  ```
  Reference position (risk-tier ceiling 5.0% size, entry 100.00, stop 81.00)
  ```  
  Change `5.0%` to `3.0%` so the worked example aligns with the single-name cap.

- **The standalone “End every verdict with this exact line” instruction outside JSON**, because it conflicts with the JSON-only rule:  
  ```
  End every verdict with this exact line:
    Worked example — classroom simulation, not financial advice.
  ```  
  Either delete it or rephrase as “Include this exact sentence inside the `narration` field.”

**Load-bearing items that must stay**

- The grounding directive:  
  ```
  Use only the facts and numbers explicitly provided in this prompt. Do not assume, infer, invent, or recall any datum you were not given...
  ```
- The user mandate caps and flags: max drawdown 30%, single-name 3.0%, sector 40.0%, long-only, trading pace, open-risk cap, cooldown.
- The safety floor rules and the final JSON schema with exactly `APPROVE`/`PASS`.
- The AAPL fact sheet with reference price, valuation, ranges, catalysts, and the explicit “use only numbers from the data block above” instruction.
- A corrected, internally consistent portfolio state table.