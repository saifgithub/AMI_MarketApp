# WP13 — R58: debate-order randomization (code + measured experiment)

**Worker model: Sonnet.** **Wave 1 — you are the ONLY lane allowed to edit
`backend/app/services/room_runner.py` in this wave.** Land it cleanly; WP14/WP15
queue behind you.

## Source design

`../fable/05_further_improvements.md` §12. Bull always speaks before Bear
(`PHASES` at `room_runner.py:169-191`, RESEARCHERS phase); LLM judges anchor on
order and the RM reads both. Two deliverables: the seedable order mechanism, and
the replay measurement. The DEFAULT DOES NOT CHANGE — flipping it is Saiful's
call, made on your measurement.

## Part A — code (small, surgical)

- Config: `room_debate_order_seeded: bool = False` in
  `backend/app/core/config.py`, forwarded in `docker-compose.yml`'s `api-alpha`
  block (`test_config_compose_parity.py` enforces the pair).
- When `True`: the RESEARCHERS phase's agent order is a deterministic function of
  the run id (stable for that run and its replays; ~50/50 Bull-first/Bear-first
  across runs). `PHASES` is a frozen module-level tuple — apply the ordering at
  iteration time in the runner loop, don't mutate the table. RISK-phase debator
  order is OUT of scope (three-way, different question).
- **`test_cr077_phase_parallelism.py` must stay green untouched**: the parallel
  set stays EXACTLY `{ANALYSTS}`; RESEARCHERS stays sequential — you are
  reordering a sequential phase, not parallelizing it.
- The served order is visible in the stored transcript (turn order IS the
  record); add one structured log line naming the order chosen so a batch can be
  audited without parsing transcripts.
- Tests: seeded determinism (same run id ⇒ same order), distribution sanity
  (both orders occur across ids), flag-off ⇒ exactly today's order, CR077 guard
  green.

## Part B — the experiment (harness)

- Extend the CR219 harness (`docs/forward_planning/CR219_room_prompt_contradictions/harness/`
  — read its README/`pm_replay.py` for the idiom) with a debate-order replay:
  same banked context, both orders, through RESEARCHERS → SYNTHESIS at minimum
  (the RM stance is the primary read); carry to EXECUTION+VERDICT if the harness
  supports the chain without new plumbing.
- N ≥ 20 distinct contexts from the golden set × both orders. LLM: LAN-direct
  `http://192.168.20.74:8048`; verify identity by reading `root` from
  `/v1/models` first (never trust the `ami-llm` alias) and name the model in the
  results file.
- Results memo: `harness/results/2026-09-03_R58_debate_order.md` + raw JSON —
  does order move the RM stance distribution / PM verdict beyond parse-noise
  (compare against the R47 file's parse-loss rates for what "noise" is)? End
  with a recommendation (keep fixed order / adopt seeded / summarize-then-debate)
  and the explicit line that the default ships unchanged pending Saiful.

## Lane discipline (shared checkout, 30+ live sessions)

- Touch ONLY: `room_runner.py` (order seam), `config.py`, `docker-compose.yml`
  (one line), harness files under the CR219 folder, your new tests.
- Pathspec-commit only (`git commit -m "…(AT:R75 CR219)" -- <files>`); `git add
  <exact path>` first for new files; never bare / `-am` / `add -A`.
- Never edit `issue_register.md` / `cr_list.md` / `def_list.md`.
- Tests: `backend/.venv/bin/pytest backend/tests/unit/ -q`; new tests pass from
  BOTH repo root and `backend/` CWDs (paths from `__file__`).
- Report commit hashes + test tail + the results memo path; the dispatcher
  verifies by forensics + rerun and will announce "WP13 accepted" to unblock the
  queued lanes.
