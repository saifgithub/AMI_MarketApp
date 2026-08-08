# External review — portfolio_manager

> Reviewer: `kimi-for-coding` · reasoning tokens 14955 · prompt 3546 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

1. JOB

The Portfolio Manager must emit a single JSON object that either **APPROVEs** the AAPL trade with `size_pct`, `entry`, `stop`, `target`, `horizon_days`, and a 3–4 sentence `narration`, or **PASSes** with only `narration`, after applying the user mandate and safety floor.

---

2. CONTRADICTIONS

- **Allowed verdict values.** The prose template says:
  ```
  Verdict:   APPROVE | REJECT | MODIFY-AND-APPROVE
  ```
  The final binding instruction says:
  ```
  There are exactly two action values: APPROVE and PASS.
  ```
  and
  ```
  Do NOT write 'MODIFY', 'MODIFY-AND-APPROVE', or any other value — they are discarded and your verdict is lost.
  ```

- **What to do on a compliance violation.** The decision sequence says:
  ```
  If compliance fails → REJECT with the specific violation. Done.
  ```
  The safety floor says:
  ```
  YOU MUST REJECT any trade that:
  1. Violates user.compliance.* ...
  ```
  but then immediately says:
  ```
  If a violation is detected, your output MUST be:
  {
    "action": "PASS",
    "narration": "<state the specific mandate rule violated and that no trade is being proposed>"
  }
  ```
  It tells the model both to “REJECT” and to output `{"action": "PASS"}`.

- **Output container.** The profile template demands:
  ```
  ## Output format
  ...
  Tag:       Worked example — classroom simulation, not financial advice.
  ```
  while the final binding instruction demands:
  ```
  Your ENTIRE reply must be one single JSON object — begin with '{' and end with '}'. Do not write any prose outside the JSON ... anything outside it is discarded and your verdict is lost.
  ```
  The safety floor also insists:
  ```
  End every verdict with this exact line:
    Worked example — classroom simulation, not financial advice.
  ```
  A pure JSON object cannot end with a non-JSON tag line.

- **Trade schema.** The profile template asks for:
  ```
  Final trade (if approved/modified):
    Instrument, Side, Size, Entry, Target, Stop, Horizon
  ```
  The binding schema says:
  ```
  Shape it exactly like:
  {"action": "APPROVE" | "PASS",
   "size_pct": <number...>,
   "entry": <number...>,
   "stop": <number...>,
   "target": <number...>,
   "horizon_days": <integer...>,
   "narration": "..."}
  ```
  There is no `instrument`, `side`, or `mandate_compliance` field, and adding them would violate “shape it exactly like.”

- **Single-name cap vs. the supplied portfolio.** The mandate says:
  ```
  Single-name position-size cap: 3.0% of portfolio in any one name
  ```
  The simulated portfolio state says:
  ```
  Open positions:
    MSFT ×40 (26.1% of portfolio, unrealised +796.00)
  ```
  The prompt hands the agent a position that already breaches the same 3% ceiling it is told to enforce.

---

3. UNFOLLOWABLE

- **Required upstream inputs are missing.** The prompt lists:
  ```
  - Trader's proposal
  - Research Manager's synthesis
  - All 3 Risk Debators' arguments
  ```
  and instructs:
  ```
  Weigh the Bull/Bear synthesis from the Research Manager
  Weigh the 3 Risk Debators
  ```
  and:
  ```
  Do not just restate the Trader's numbers; agree or disagree based on the whole debate.
  ```
  None of these inputs appear in the prompt, so the model cannot weigh them or agree/disagree with the Trader.

- **“Only use numbers in the data block” conflicts with producing a trade plan.** The prompt says:
  ```
  Use specific numbers wherever possible — but ONLY numbers from the data block above.
  ```
  But the binding JSON requires:
  ```
  "size_pct": <number, required if APPROVE>
  "entry": <number, required if APPROVE>
  "stop": <number, required if APPROVE>
  "target": <number, required if APPROVE>
  "horizon_days": <integer, required if APPROVE>
  ```
  The data block contains no proposed trade plan, only a reference price, ranges, and fundamentals. An `APPROVE` therefore cannot be filled without inventing numbers.

- **Hard compliance checks require data the prompt does not contain.** Examples:
  - Drawdown cap:
    ```
    Max acceptable drawdown: 30% — a PORTFOLIO-level cap on total drawdown
    ```
   