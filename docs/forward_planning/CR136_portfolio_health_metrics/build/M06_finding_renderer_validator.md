# CR136 build — M06: Finding renderer + validator + LLM path

> Conforms to CR136 Rev 4 + build/README.md. Where this doc and Rev 4 disagree, Rev 4 wins.

## 1. Purpose

Implements Rev 4's **"The Finding"** (head disclosure F19, §F1–§F5, register split),
the **"LLM prompt contract"** (strip-before-assembly, precomputed comparisons,
sectioned-JSON output, the Rev 4 post-generation validator — the Rev 3 digit-sequence
rule is DELETED and must not be implemented), and the app-level persistence half of
the **"Journal storage plan"** (idempotency on `(portfolio_id, as_of)`; the same read
supplies `rule_states` to M05's hysteresis). One new backend service module. The LLM
is optional and config-gated; **every path ends in a complete, correct report**
(CR040): any validation failure or provider unavailability serves the deterministic
rendering, which emits only registered tokens and therefore validates by construction.

## 2. Files

**New**

- `backend/app/services/portfolio_finding.py` — header docstring one-liner:
  `"""Portfolio Health Finding (CR136 M06) — deterministic §F1–§F5 renderer with head disclosure, closed numeric allow-list validator + register check for the optional LLM narration path, and journal persistence with (portfolio_id, as_of) idempotency."""`
- `backend/tests/unit/test_cr136_finding_renderer.py` — header:
  `"""CR136 M06 — strip test, deterministic templates, §F1 word cap, §F5 speech act, head disclosure, idempotency."""`
- `backend/tests/unit/test_cr136_finding_validator.py` — header:
  `"""CR136 M06 — allow-list validator: rounding paths, scale-aware lookup, register lexicon, LLM fallback."""`

**Touched**

- `backend/app/core/config.py` — add `portfolio_health_llm_enabled: bool = True`
  (style: flat Settings fields with a why-comment, cf. `llm_force_provider` at
  config.py:120, `use_real_market_data` at config.py:141).
- `docker-compose.yml` — forward `PORTFOLIO_HEALTH_LLM_ENABLED` in the `api-alpha`
  environment block; `backend/tests/unit/test_config_compose_parity.py` fails
  otherwise (CR040 / DEF038 / DEF063).
- `backend/app/services/portfolio_health_constants.py` (M04's shared constants
  module — M04 owns creation and pins the final path; symbols below are the
  contract): M06 **adds** its validator constant blocks beside `SUFFICIENCY`,
  per Rev 4 validator category (c) "checked in beside SUFFICIENCY".

**Verified anchors (HEAD, 2026-08-02)** — all under `backend/app/` unless noted:
`get_llm_gateway()` services/llm_gateway.py:735; `LLMGateway.stream_chat`
llm_gateway.py:650 (async chunk generator; prepends the CR056 grounding directive
itself at :670 — do NOT duplicate it); `has_real_provider()` llm_gateway.py:596;
`extract_json_object` services/llm_json.py:14; collect-stream idiom
`_stream_to_string` services/brief_engine.py:438; journal append + `EntryType(...)`
coercion (raises on unknown strings) services/journal_store.py:81-115 (coercion
:84-86); `list_for_user` journal_store.py:117 (Floor Pass 30-day retention filter
:127-136); `entry_type` is a plain String column db/models.py:267 (no migration);
`EntryType` enum schemas/journal.py:25-34; `disclaimerShort` = "Educational
simulation. Not investment advice." mobile/lib/l10n/app_en.arb:1362;
`reset_portfolio` is destroy-and-recreate services/sim_engine.py:394-403 (series
keyed to `portfolio_id` never spans a reset — no handling needed here); DEF210
parity mechanics tests/unit/test_journal_entry_type_parity.py:56-77 (a new backend
enum member fails the suite until the Dart `fromWire` case ships — see §4/§7).

## 3. Implementation spec

### 3.1 Constants consumed / contributed (shared constants module, M04)

Consumed (M04-owned): `ENGINE_VERSION = "cr136.v1"`, `SUFFICIENCY`,
`SCENARIO_EPISODES`. Consumed (M05-owned, per README contract 3): the rule
evaluator and `RULE_TEMPLATES: dict[str, str]` (verbatim Rev 4 rule-table
templates; M06 renders them by `str.format(**slots)`).

Contributed by M06 (into the shared constants module; every constant carries a
comment naming its Rev 4 derivation):

```python
REGISTER_LEXICON = (            # Rev 4 register check — the 20 terms, verbatim
    "shrinkage", "covariance", "OLS", "R²", "standard error", "estimator",
    "regression", "confidence interval", "kurtosis", "Ledoit", "Markowitz",
    "Choueifaty", "CAPM", "pro-forma", "eigen*", "quadratic", "sampling error",
    "heteroskedastic*", "JPM", "EWMA",
)
F1_MAX_HEADLINE_WORDS = 16      # shipped as HEADLINE_MAX_WORDS (Rev 4 §F1)
F1_PARTIAL_MARKER = " (partial data)"   # +2 tokens; templates sized ≤14 so cap holds
# AT:R66: the shipped RAW set also carries "0" — "no commissions, spreads, or
# taxes" and the zero-cost line put a bare 0 in mandated prose, and a fixed set
# that cannot pass its own required content is the Rev 3 failure repeating.
VALIDATOR_FIXED_RAW = {         # category (c), RAW set. Closure is enforced by the
    # deterministic self-validation test — any template edit adding a literal
    # MUST extend this set or that test fails.
    "1952", "2004", "2008",     # citation years: Markowitz; Ledoit & Wolf; Choueifaty & Coignard
    "252", "504", "126", "21",  # annualisation, data window, sufficiency floor, month
    "1.96", "1.645", "0.97",    # z 95% CI, z bad-month, λ
    "500",                      # "S&P 500" tokenizes as 500
    "30", "4", "3", "6", "2",   # fat-tail block: κ≈30 crash bound, 4.0× factor, κ 3–6 range, §5.3.2 tail
    "5.3",                      # "§5.3.2" tokenizes as 5.3 + 2
    "1", "20",                  # "1-in-20 bad month"
    "10", "10000",              # $10k / $10,000 starting capital
    "11", "12",                 # BOK lessons M11/M12 cross-reference
    "2020", "2022",             # scenario episode display years
}
VALIDATOR_FIXED_PCT = {         # category (c), PCT set
    "95",                       # 95% CI
    "40",                       # R1 template literal "more than 40%"
    "97",                       # Barber & Odean zero-cost line
    "2.0", "2.5", "10", "13",   # fat-tail honesty range: 2.0–2.5pp = 10–13%
}
RULE_SLOT_SCALE = {             # category (b): scale per numeric slot, per rule.
    # Non-listed slots are text and are not registered as numbers.
    "R0": {"cap": "pct", "weight": "pct"},
    "R1": {"risk_share": "pct", "weight": "pct",
           "threshold_mention": "pct"},   # AT:R66 — R1's template says "more than
                                          # 40%"; the slot carries that literal so
                                          # the closure test covers it (F15)
    "R2": {"n": "raw", "dr2": "raw"},
    "R2b": {"rho": "raw"},
    "R3": {"beta": "raw", "r2_pct": "pct", "window": "raw"},
    "R4": {"cash": "pct"},
    "R5": {"covered": "pct"},
}
F5_FORBIDDEN_IMPERATIVES = (    # §F5 speech-act guard: sentence-initial verbs
    "buy", "sell", "trim", "cut", "reduce", "add", "increase", "decrease",
    "rebalance", "hedge", "diversify", "exit", "close", "open", "rotate",
    "shift", "move", "switch", "take", "avoid",
)
F5_FORBIDDEN_PHRASES = (        # anywhere in §F5, case-insensitive
    "you should", "you must", "you need to", "we recommend", "we suggest",
    "consider selling", "consider buying", "consider trimming",
)
NON_STATIONARITY_CAVEAT = (     # Rev 4 §F3 verbatim pin — byte-for-byte
    "These estimates describe the window just past. In market stress, "
    "correlations between holdings rise sharply — diversification measured in "
    "calm markets can overstate the protection available in a crisis."
)
ETF_OVERLAP_DISCLOSURE = (      # Rev 4 F21 verbatim pin
    "counts each ETF as one holding; index-fund overlap is not looked through — "
    "your true single-name exposure can be higher."
)
PORTFOLIO_HEALTH_ENTRY_TYPE = "portfolio_health_analysis"
```

### 3.2 Context builder — strip BEFORE anything

```python
def build_stripped_context(metric_blocks: list[dict], *, as_of: str) -> dict
```

Returns `{"as_of": as_of, "metrics": [<blocks>]}` containing **only** blocks with
`sufficient` truthy. A stripped block is dropped **entirely — key, metric name,
every field**. This runs before template selection AND before any prompt string is
built; the model and the templates never see an insufficient metric's name (Rev 4
uncertainty contract). Zero sufficient blocks ⇒ raise `InsufficientContextError`
(M07 maps it to the not-enough-data state; the F20 our-limit copy is owned by
M07/M09, not rendered here).

### 3.3 Deterministic renderer

Head disclosure — `render_head_disclosure(context) -> str` — ALWAYS deterministic,
on both paths; the LLM never generates it (F19). Verbatim template (markdown
blockquote; line 1 must equal `disclaimerShort`, app_en.arb:1362; new EN strings —
`retranslate:[ar,ms]`):

```text
> **Educational simulation. Not investment advice.**
> All figures are gross of fees — this simulation charges no commissions, spreads, or taxes; live trading does.
> Every forward-looking number below is a backcast: today's holdings weighted against past returns. It is not a forecast.
> Window: {window_days} trading days, {n_observations} observed returns; estimator: EWMA-weighted covariance, λ=0.97, effective sample ≈ {t_eff} days.
> {NON_STATIONARITY_CAVEAT}
```

`t_eff` rendered at 1 dp (RAW admits 1–4 dp — 0 dp would NOT validate). The head
block and §F3/§F4 are exempt from the register check by design (they name the
estimator); §F1/§F2/§F5 are not.

`render_deterministic_sections(context, rule_results) -> dict[str, str]` — keys
`"f1"…"f5"`. All number formatting via `Decimal` with `ROUND_HALF_UP` (one of the
two admitted roundings ⇒ self-validates). PCT display dp: §F1 shares 0 dp, vol/TE/
bad-month/MDD/scenarios 1 dp, §F3 values 2 dp. RAW: beta 2 dp, DR² 1 dp, ρ 2 dp,
HHI 3 dp, t_eff 1 dp.

**§F1** — 3–5 headlines, one per sufficient source block, ≤14 template tokens so
`F1_PARTIAL_MARKER` (+2) keeps them ≤16 (`retranslate:[ar,ms]`):

| headline (rendered only when its block is sufficient) | tokens |
|---|---|
| `Annualised volatility {sigma_p}%; the S&P 500 measured {sigma_b}% over the same window.` | 12 |
| `{ticker} drives {risk_share}% of risk while holding {money_share}% of invested money.` | 11 |
| `{n_holdings} holdings currently behave like {dr2} effective independent bets.` | 9 |
| `Deepest fall in the last {mdd_window} trading days: {mdd}% peak-to-trough.` (Tier 2) | 10 |
| `Moved about {beta}× the S&P 500; the market explains {r2_pct}% of daily moves.` | 13 |

When `low_explanatory_power` is set, the beta headline inserts `only`:
`… the market explains only {r2_pct}% of daily moves.` (14 tokens; 16 with marker —
exactly at cap). **R² is NEVER written as "R²"/"R2" in §F1/§F2/§F5** — the plain
form above is the F19 amendment, and the literal would trip the register check by
design. Headlines built on a `partial: true` block append `F1_PARTIAL_MARKER`.

**§F2** — 4–8 sentences, descriptive only; required sentences (Rev 4 §F2), in
order: risk posture (σₚ vs σ_b + TE), diversification (DR² vs holding count WITH
the vol-imbalance caveat — DR² is never presented alone as a diagnosis: "a low
count can come from holdings that move together or from one position much larger
or more volatile than the rest"), concentration (top contributor, invested basis),
optional beta sentence, and the window + sufficiency + backcast sentence (with the
partial clause `, excluding {dropped_list} ({covered}% of invested value covered)`
when partial). Forbidden: advice verbs, mean-return/performance claims, any number
not in the payload.

**§F3 units (AMENDED, M06 audit AT:R66)** — the value and SE are rendered
through `METRIC_VALUE_UNIT`, the pinned per-metric unit map in the shared
constants module: Tier-1 values are decimal fractions (×100 to display), Tier-2
`realised_*` values are already percent (never ×100), and `beta` /
`effective_bets` / `weight_concentration` are dimensionless ratios that take no
percent sign at all — including their standard errors. An unpinned metric id
raises. Applying the Tier-1 convention to a Tier-2 block published a 19.69% fall
as "1969.00%" in §F3 while §F1 rendered the same block as 19.7%, and the
allow-list registered BOTH readings, so the wrong one validated. The unit map is
now consulted by the renderer and the allow-list builder alike.

**§F3** — one block per sufficient metric: display name, value + SE where defined
(`(standard error {se}, T_eff {t_eff})`; DR²/shares/MCR render "standard error:
null by design — stability is handled by rule hysteresis"), `{n_observations}`
returns over `{window_days}` trading days, estimator name + citation, a fixed
what-this-measures one-liner, data-quality note (dropped holdings + reasons when
partial). The weight-concentration block appends `ETF_OVERLAP_DISCLOSURE` when
`contains_etfs`. Scenario blocks are labelled backcast what-ifs with the R² share
stated, episode names rendered as fixed strings `COVID crash (Feb–Mar 2020)` /
`2022 drawdown (Jan–Oct 2022)` (year tokens are in `VALIDATOR_FIXED_RAW`; episode
return values are numeric leaves of the block, category (a)).

**§F3 standing disclosures** — a fixed block appended to §F3 **on both paths**
(deterministic append even under LLM narration — prompt instructions are not
controls, CR038; this is what makes the mandated content structural). Content,
covering every Rev 4 §F3 "required once" item (`retranslate:[ar,ms]`): estimator
disclosure ("EWMA-weighted sample covariance, λ=0.97 (RiskMetrics Technical
Document, 4th ed., §5.3.2), weighted-demeaned, over the risky holdings plus the
SPY benchmark leg; effective sample ≈ {t_eff} days; chosen because an equal-weight
window re-prices an old shock the day it leaves the window — EWMA responds at the
event"); no-shrinkage note (Ledoit & Wolf 2004; measured alarm suppression);
citations Markowitz (1952), Choueifaty & Coignard (2008), CAPM; fat-tail honesty
("at a window-realistic excess kurtosis of 3–6 the standard error is likely
2.0–2.5pp (10–13% of the estimate); a crash-inclusive window (excess kurtosis near
30) raises the inflation factor to 4.0×"); the IID/√252 caveat; the
gross-of-fees-plus-zero-cost-simulation line; the backcast statement; `NON_STATIONARITY_CAVEAT`
verbatim; "Related lessons: M11 and M12 in the Body of Knowledge." Every numeric
literal in this block is in the FIXED sets — the mandated-content test proves it.

**§F4** — 2–4 sentences tying risk level, diversification, concentration;
restates window and limits; **no new numbers** (may repeat already-rendered ones).

**§F5 "What the numbers point to"** — conditional-educational speech act ONLY
(Rev 4 pin): each item is a fired rule's template from M05's `RULE_TEMPLATES`
rendered with its slots — a general textbook statement with the user's own number
as the trigger; never imperative, no severity bands, no "you should". When R0 or
R1 fired, append the zero-cost line: "A note beside any trimming thought: this
simulation charges no commissions, spreads, or taxes. In measured brokerage data
(Barber & Odean), about 97% of the penalty from frequent trading is invisible at
zero cost." None fired ⇒ "No review threshold was crossed this run. The sections
above describe the measured book; nothing here rose to a textbook response."
(`retranslate:[ar,ms]`.)

Unknown `metric` id in a sufficient block ⇒ raise `ValueError` (degrade loudly —
never a silent skip). The renderer's display map must cover exactly M04's frozen
metric-id set.

### 3.4 Validator — closed allow-list, scale-aware (Rev 4; digit rule DELETED)

```python
@dataclass
class Allowlist:
    pct: set[Decimal]   # normalized Decimals
    raw: set[Decimal]

def build_allowlist(context: dict, rule_results: list[dict]) -> Allowlist
def tokenize_numbers(text: str) -> list[NumToken]   # value, scale, raw_text, section-relative span
def validate_sections(sections: dict[str, str], allowlist: Allowlist) -> ValidationFailure | None
```

Allow-list build, per Finding, from the **same stripped context**:

- **(a)** every numeric leaf of every sufficient block (recursive walk of dicts/
  lists; `int`/`float` leaves; **exclude `bool`** — `True` is an `int` in Python —
  and `None`): PCT set gets value×100 rendered at 0, 1, 2 dp; RAW set gets the
  value at 1, 2, 3, 4 dp **plus verbatim** (`Decimal(str(v)).normalize()`). Each
  rendering under BOTH `ROUND_HALF_UP` and `ROUND_HALF_EVEN`, each **±1 ulp at its
  dp** (at dp d, also admit rendered ± 10⁻ᵈ). Corollary: 0-dp percent tokens carry
  the documented ±1pp accept window.
- **(b)** every value the rule engine interpolated into any template: for each
  fired rule, each slot named in `RULE_SLOT_SCALE[rule_id]` joins its scale's set
  (rendered value verbatim + ±1 ulp at its rendered dp).
- **(c)** `VALIDATOR_FIXED_PCT` / `VALIDATOR_FIXED_RAW` verbatim.
- **(d)** `n_observations`, `window_days`, and holding counts, verbatim integers,
  into RAW.
- Sign tolerance (M06 pin): for every registered value, the absolute-value alias
  is registered in the SAME set ("fell 33.9%" vs a stored −0.339 — a false reject
  here only churns the fallback, but the alias never crosses scale sets).

Normalization: tokenize digit groups with
`[−-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[−-]?\d+(?:\.\d+)?` (thousands separators only
as comma-grouped 3s — `1, 2` stays two tokens); strip separators; map U+2212 to
`-`; `Decimal(token).normalize()`. A token followed (≤1 space) by `%`, `pp`,
`percent`, or `percentage point` looks up **PCT**; else **RAW**. **Scale-aware
lookup, NEVER the union** — the union was measured to false-accept "Your beta
is 62." Membership = normalized-Decimal set lookup.

Rejection: ANY non-member token ⇒ **discard the ENTIRE model output**, log
`logger.error("portfolio_finding_llm_rejected", reason="unregistered_number",
section=<id>, tokens=[...])` (degrade loudly), serve the deterministic rendering.
The deterministic renderer emits only registered tokens ⇒ validates by
construction; it is therefore NOT re-validated at runtime (no rejection loop with
no fallback left) — the by-construction guarantee is enforced by the
self-validation unit test instead.

Validator scope: sections f1–f5 of LLM output only. Head block, title, summary
are deterministic always.

### 3.5 Register check (same rejection path)

```python
def register_check(sections: dict[str, str]) -> ValidationFailure | None
```

- **§F1/§F2/§F5 only** (§F3/§F4 and the head block exempt): no match of any
  `REGISTER_LEXICON` term — case-insensitive, word-boundary; `eigen*` /
  `heteroskedastic*` are prefix wildcards (`\beigen\w*`); R² also matches
  `\bR\^?2\b` and `R²`.
- **§F1**: each headline ≤ `F1_MAX_HEADLINE_WORDS` whitespace-split tokens.
- **§F5 imperative guard** (runtime, LLM path — the speech-act pin must hold
  structurally, CR038): reject if any §F5 sentence begins with a
  `F5_FORBIDDEN_IMPERATIVES` verb (case-insensitive) or any
  `F5_FORBIDDEN_PHRASES` phrase appears.
- Any violation ⇒ same rejection path as 3.4 (`reason="register_lexicon"` /
  `"headline_length"` / `"imperative"`).

### 3.6 LLM path (optional, config-gated)

```python
async def llm_render_sections(
    context: dict, rule_results: list[dict], gateway: LLMGateway, *, user_id: UUID,
) -> dict[str, str] | None
```

- Gate: `settings.portfolio_health_llm_enabled` AND `gateway.has_real_provider()`
  (llm_gateway.py:596) — else return `None` immediately
  (`logger.info("portfolio_finding_llm_skipped", reason=...)`). The mock provider
  must never narrate a Finding.
- Prompt: system prompt (skeleton below) + one user message containing the
  stripped-context JSON, the fired rules' rendered template texts, and the
  precomputed comparisons (benchmark σ, TE, scenario constants — already leaves of
  the context; **if a comparison is not in the payload, it is not said**).
  System-prompt pins (Rev 4 prompt contract): the verbatim sentence
  *"Number-bearing statements about volatility, beta, diversification and risk
  contribution describe the measured window only and are backcasts of today's
  holdings"*; register instructions (f1/f2/f5 plain language, no statistics
  jargon; explanatory power ONLY as "the market explains X% of this book's
  day-to-day moves", never R-squared); f1 = 3–5 headlines ≤16 words each; f2 =
  4–8 descriptive sentences, no advice, no performance claims; f4 = 2–4
  sentences, no new numbers; f5 = the provided rule texts only, lightly
  connected, nothing that reads as an instruction to trade; output ONLY the JSON
  object `{"f1": ["…"], "f2": "…", "f3": "…", "f4": "…", "f5": "…"}`. The
  gateway prepends the CR056 grounding directive itself (llm_gateway.py:670).
- Call: `gateway.stream_chat(system_prompt=…, messages=[…], model_tier="mid",
  max_tokens=4096, audit_user_id=user_id, audit_agent_id="portfolio_health",
  audit_flow="portfolio_health_finding")`, collected to a string
  (brief_engine.py:438 idiom). `model_tier` is fixed — `tier_policy.pick_tier`
  (tier_policy.py:22) is per-(plan, agent) and defines no portfolio-health agent;
  vLLM serves a single model regardless.
- Parse: `extract_json_object` (llm_json.py:14); require all five keys, `f1` a
  list of strings (joined as markdown bullets), f2–f5 strings ⇒ else schema
  failure. Then `validate_sections` + `register_check` on the result.
- **ANY failure** — provider exception, empty output, schema failure, validator or
  register rejection — returns `None`; the caller serves the deterministic
  sections and records the reason. Never a partial merge of LLM and deterministic
  prose within f1–f5; §F3's standing-disclosures block (3.3) is the one
  deterministic append made on both paths.

### 3.7 Orchestrator + persistence

```python
class InsufficientContextError(Exception): ...

@dataclass
class FindingResult:
    entry: JournalEntry
    created: bool                 # False = idempotent replay of the prior entry
    llm_used: bool
    llm_rejected_reason: str | None

def load_latest_finding(store: JournalStore, user_id: UUID, portfolio_id: UUID) -> JournalEntry | None

async def generate_and_persist_finding(
    *, user_id: UUID, portfolio_id: UUID, as_of: str,       # ISO date of evaluation
    metric_blocks: list[dict], store: JournalStore,
    evaluate: Callable[[dict], tuple[list[dict], dict]],    # REQUIRED, no default
    gateway: LLMGateway | None = None,
) -> FindingResult
```

> **AMENDED (M06 audit, AT:R66).** Two signature corrections, both from
> build/README.md's seam register, which overrides this doc:
>
> - The name is **`generate_and_persist_finding`**, as the register pins it —
>   not `generate_finding`. M07 codes against the register.
> - **`evaluate` is a required keyword argument with no default.** M06 renders
>   rules; it does not own their inputs (mandate, holdings, ρ), which live in
>   M04's context, so M07 binds M05's `evaluate_rules` to them and passes the
>   closure. The first implementation defaulted it to `None` and raised
>   `ValueError` at runtime; a caller built to this doc's earlier signature hit
>   that on every generating call. Requiring it makes omission a `TypeError` at
>   the call, and no default is defensible — a no-rules default would publish a
>   Finding whose §F5 says nothing fired, with no signal that the rules never
>   ran.

- `load_latest_finding`: `store.list_for_user(user_id, plan=Plan.FLOOR_MANAGER,
  entry_type=PORTFOLIO_HEALTH_ENTRY_TYPE, limit=50)` — `FLOOR_MANAGER` because
  this is an internal system read and the Floor Pass 30-day retention filter
  (journal_store.py:39, :127-136) must not hide hysteresis state from the engine —
  then filter `payload["portfolio_id"] == str(portfolio_id)`, newest first.
  Soft-deleted rows are excluded here (M07's trial counter includes them; this
  read intentionally does not — a deleted Finding may be regenerated).
- `generate_finding` flow: (1) `build_stripped_context` (raises
  `InsufficientContextError` on zero sufficient blocks); (2) `load_latest_finding`
  — ONE read serving both concerns: if prior `payload["as_of"] == as_of` ⇒ return
  `FindingResult(entry=prior, created=False, …)` — no LLM call, no write
  (`logger.info("portfolio_finding_idempotent_hit")`); (3) prior
  `payload["rule_states"]` (default `{}` = all cleared — Rev 4: first Finding
  starts cleared) is passed to M05's evaluator (name per M05's doc; result shape
  frozen by README contract 3); (4) render deterministic sections; if the LLM
  path returns validated sections, use those for f1–f5 (head + §F3 standing
  disclosures stay deterministic); (5) append via
  `JournalEntryCreate(user_id=…, entry_type=EntryType(PORTFOLIO_HEALTH_ENTRY_TYPE),
  title=…, summary=…, payload=…)` — the enum member is resolved **lazily from the
  string constant at call time** so this module imports cleanly before M08 lands
  the member (the call raises `ValueError` loudly until then — see §7).
- Title: `Portfolio Health — Finding {as_of}`; summary: first headline of the
  final f1 (`retranslate:[ar,ms]`).
- Payload (README contract 5, stored verbatim; mobile renders the STORED
  sections): `{"engine_version": ENGINE_VERSION, "portfolio_id": str,
  "as_of": str, "sections": {"head", "f1"…"f5"},
  "context": <stripped context>, "rules_fired": [{rule_id, slots, based_on}],
  "rule_states": {…}, "llm_used": bool, "llm_rejected_reason": str|None}`.
  The head disclosure is stored in the payload — the archived artefact carries
  its own disclosures forever (F19).

> **AMENDED (M06 audit, AT:R66).** The head block lives **inside `sections`**,
> under the key `head`, exactly as the seam register pins the payload shape. The
> first implementation hoisted it to a sibling `head_disclosure` key, and the
> frozen-payload test asserted that shape — so the suite certified the drift
> instead of catching it, and a consumer built to the pin would have hit
> `KeyError: 'head'` with everything green. It is added at payload-assembly
> time, so the validator and the register check still see exactly the five
> model-narratable sections.

## 4. Out of scope for this module

- Metric computation, block schema, Σ, sufficiency — **M04** (M06 consumes blocks
  as given; the metric-id set and per-holding breakdown field are frozen in M04's
  doc).
- Rule thresholds, hysteresis state machines, template WORDING — **M05** (M06
  renders `RULE_TEMPLATES` and registers slot values; it never decides firing).
- `EntryType.PORTFOLIO_HEALTH_ANALYSIS` enum member, Dart `fromWire`/`wire`
  mapping, `test_journal_entry_type_parity.py` update — **M08** (adding the
  backend member alone fails the DEF210 parity suite,
  test_journal_entry_type_parity.py:56-65; M06 resolves the type lazily from
  `PORTFOLIO_HEALTH_ENTRY_TYPE` and unit-tests persistence against a fake store).
- API endpoint, access gating, trial/daily-cap accounting, the F20 our-limit
  not-enough-data response copy — **M07**.
- Card tiles, Finding detail screen, journal markdown branch — **M09**.
- Backfill, live verification, promotion — **M10/M11**. CR137 Room consumption.

## 5. Tests

`backend/tests/unit/test_cr136_finding_renderer.py` — fixtures: a full synthetic
stripped context (every block sufficient, plausible values), M05-shaped rule
results with test slots, a `FakeJournalStore` (in-memory `append`/`list_for_user`,
no enum coercion).

- `test_strip_insufficient_name_absent_from_prompt` — σₚ block
  `sufficient: false` ⇒ `"portfolio_volatility"` (and its display name) appears
  NOWHERE in the assembled prompt strings.
- `test_strip_insufficient_name_absent_from_deterministic_output` — same context ⇒
  nowhere in head + f1–f5.
- `test_head_disclosure_in_sections_and_payload` — rendered output starts with the
  head block; `payload["head_disclosure"]` carries the same text; line 1 ==
  app_en.arb:1362 `disclaimerShort` text; `NON_STATIONARITY_CAVEAT` present
  byte-for-byte.
- `test_f1_word_cap` — every headline ≤16 whitespace tokens, with widest slot
  values AND the partial marker appended; the low-R² beta headline == 16 exactly.
- `test_f1_r2_plain_language` — `low_explanatory_power` set ⇒ "the market explains
  only" phrasing present; `R²`/`R^2`/bare `R2` absent from f1/f2/f5.
- `test_f5_no_rule_fired_plain_statement`.
- `test_f5_templates_no_imperatives` — all rules fired: no §F5 sentence begins
  with a `F5_FORBIDDEN_IMPERATIVES` verb; no `F5_FORBIDDEN_PHRASES` match.
- `test_f5_zero_cost_line_beside_trimming` — R1 fired ⇒ zero-cost line present;
  no trim-flavoured rule fired ⇒ absent.
- `test_deterministic_self_validates_zero_rejections` — full context + all rules
  fired: `validate_sections` AND `register_check` over the deterministic f1–f5
  and head return `None` (0 rejections). This test is the closure guard on the
  FIXED constant sets.
- `test_unknown_metric_id_raises`.
- `test_idempotency_two_generates_same_day_one_entry` — two `generate_finding`
  calls, same `(portfolio_id, as_of)`: one `append`, second returns
  `created=False` with the first entry's id; no LLM call on the second (spy
  gateway).
- `test_prior_rule_states_reach_rule_engine` — capture-evaluator sees the prior
  payload's `rule_states`; first Finding sees `{}`.
- `test_zero_sufficient_blocks_raises_insufficient_context`.

`backend/tests/unit/test_cr136_finding_validator.py`:

- `test_mandated_f3_content_passes` — the rendered §F3 (per-metric blocks + the
  standing-disclosures block) passes the validator with zero rejections (the case
  that killed the Rev 3 digit rule).
- `test_fabricated_number_rejected` — context beta 1.30; text "beta of 1.9" ⇒
  rejected, `reason="unregistered_number"`, tokens + section in the failure.
- `test_rounding_paths` — payload 0.6249 ⇒ "62%" accepted; payload 0.6251 ⇒
  "63%" accepted (Rev 4 acceptance pair).
- `test_half_up_and_half_even_both_admitted` — payload 0.625 ⇒ "62%" AND "63%"
  both accepted.
- `test_ulp_window` — payload 0.62 ⇒ "61%" and "63%" accepted (±1 ulp at 0 dp);
  "60%" rejected.
- `test_scale_sets_never_unioned` — 0.62 present as PCT ⇒ "Your beta is 62."
  (RAW lookup) rejected — the measured union false-accept.
- `test_thousands_separator` — "$10,000" ⇒ token 10000 ⇒ accepted via FIXED_RAW;
  "1, 2" stays two tokens.
- `test_register_catches_seeded_leak` — §F2 containing "the EWMA covariance
  estimator" ⇒ rejected, `reason="register_lexicon"`.
- `test_register_passes_10_plain_paragraphs` — 10 plausible plain-language §F2
  fixture paragraphs ⇒ 0 false positives (Rev 4 measured 0/10).
- `test_register_f3_f4_head_exempt` — "covariance" in §F3 passes.
- `test_headline_length_rejection` — a 17-word LLM headline ⇒
  `reason="headline_length"`.
- `test_f5_imperative_rejected_at_runtime` — LLM §F5 "Sell half the NVDA
  position." ⇒ `reason="imperative"`.
- `test_llm_reject_falls_back_deterministic` — fake gateway streams output with a
  fabricated number ⇒ final sections are the deterministic ones, `llm_used` False,
  `llm_rejected_reason="unregistered_number"`, `portfolio_finding_llm_rejected`
  logged with tokens + section.
- `test_llm_schema_failure_falls_back` — non-JSON stream ⇒ deterministic.
- `test_llm_gated_off_by_config` — `portfolio_health_llm_enabled=False` ⇒ gateway
  never called.
- `test_no_real_provider_skips_llm` — mock-only gateway
  (`has_real_provider()==False`) ⇒ deterministic path, no narration.

## 6. Acceptance

- [ ] `pytest backend/tests/unit/test_cr136_finding_renderer.py backend/tests/unit/test_cr136_finding_validator.py -q` green on the Mac (sqlite tempfile; no network, no numpy).
- [ ] `pytest backend/tests/unit/test_config_compose_parity.py -q` green (the new Settings flag forwarded in docker-compose's api-alpha block).
- [ ] `grep -F "These estimates describe the window just past." backend/app/services/portfolio_finding.py backend/app/services/portfolio_health_constants.py` hits the verbatim caveat exactly once (single constant, no forked copies).
- [ ] `grep -n "digit" backend/app/services/portfolio_finding.py` shows no digit-sequence validator (the Rev 3 rule is deleted, not implemented).
- [ ] `grep -n "Educational simulation. Not investment advice." backend/app/services/portfolio_finding.py backend/app/services/portfolio_health_constants.py` — head block line 1 matches app_en.arb:1362 verbatim.
- [ ] Reviewer spot-check: no user-visible string says "the AI"; AMI by name only; every new EN template string in 3.3 is flagged `retranslate:[ar,ms]` in the commit message per the content-change rule.
- [ ] `pytest backend/tests/unit/ -q` fully green — including `test_journal_entry_type_parity.py`, which must be UNCHANGED and passing (proof M06 did not add the enum member early).

## 7. Hand-off

After M06, the next modules may assume:

- `portfolio_finding.generate_and_persist_finding(...)` exists with the exact
  signature in 3.7 (note the REQUIRED `evaluate` closure), returning
  `FindingResult`; `InsufficientContextError` for the M07
  not-enough-data mapping; tiles (M07 GET route) are untouched by this module and
  never require the LLM.
- The Finding artefact matches README contract 5 exactly; mobile (M09) renders
  the STORED sections and never regenerates.
- `PORTFOLIO_HEALTH_ENTRY_TYPE = "portfolio_health_analysis"` is the wire value.
  **M08 must land** the `EntryType` member (schemas/journal.py:25-34), the Dart
  `fromWire`/`wire` cases, and the parity-test update **before M07's POST
  endpoint ships live** — until M08 lands, `generate_and_persist_finding`'s lazy
  `EntryType(...)` resolution raises `ValueError` (loud by design, CR040), and
  old mobile clients degrade safely to the DEF210 UNKNOWN card after it lands.
- The validator constant blocks (3.1) live beside `SUFFICIENCY` in M04's shared
  constants module; M05's template literals are closed over by
  `VALIDATOR_FIXED_*` + `RULE_SLOT_SCALE`, enforced by
  `test_deterministic_self_validates_zero_rejections` — any later template edit
  that adds a numeric literal must extend the FIXED sets or that test fails.
- Rejection telemetry: **every** LLM-failure path logs at **error** level with a
  `reason`. `portfolio_finding_llm_rejected` (with `reason`, `section`, `tokens`)
  covers the schema and validator/register rejections;
  `portfolio_finding_llm_failed` (with `reason="provider_error"`) covers "nothing
  came back at all" — a deliberately distinct event, because an outage and a
  rejected narration are different operational facts. Both are what M11's
  verification watches in `ami_api_alpha` logs.
  > **AMENDED (M06 audit, AT:R66).** Two of the four paths originally logged at
  > WARN — the provider-exception path and the schema path. A vLLM outage and a
  > persistently malformed model, the two failure modes an operator most needs
  > to see, therefore produced no ERROR-level signal at all, which is the exact
  > silent degrade CR040 exists to surface.

**Reconciliation still owed to M07/M08 (M06 audit, AT:R66).** The seam register
pins `JournalStore.latest_portfolio_health_entry(...)` and
`JournalStore.portfolio_health_stats(...)` as **M08-owned, consumed by M07,
never re-implemented** — retention and soft-delete filters make the generic
`list_for_user` path wrong here. M06 currently carries its own
`load_latest_finding(store, …)`. When M08 lands those store methods,
`load_latest_finding` must become a thin delegate or be deleted: two
implementations of "the newest Finding for this portfolio" is precisely how the
daily cap and the hysteresis memory drift apart.
