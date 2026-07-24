<!-- intake note from the Room-quality lane (AT:R59). Not a register write. Architect owns IDs/registers. -->
# room-quality — new reference doc: Agent Data Blueprint (feeds DEF098's guard)

PROPOSED-KIND: none — informational (docs-only, already committed plain `(AT:R59)`)
SOURCE: Room-quality lane (Saiful: "build a fresh one, written as an expectation … the blueprint against which delivery is expected")
TRIAGE: FYI

**What landed:** `docs/initial_specs/02_agents/agent_data_blueprint.md` — the normative,
all-surface (Room / 1-on-1 / Brief Your Agent / Concierge) statement of the inputs each
agent MUST receive, expressed in a field-level data dictionary so a parity test can bind to
it directly.

**Why the architect needs to know:** it is the **expectation DEF098's prompt-data parity
guard should check against.** DEF098 (architect-owned) builds the guard; this file is the
per-agent, per-surface field list the guard enforces. They must stay consistent. I did **not**
touch DEF098.

**Already reflected in it (no re-file):** DEF096 (Room drops 3/6 Social fields), DEF095/DEF066
(Trader denied its own derived R:R / drawdown), and the 1-on-1 next-earnings asymmetry DEF098
documents. Supersedes the stale `agent_data_matrix.md` in CR023's research folder.

**No action requested** beyond: when wiring DEF098's guard, bind it to this blueprint's
dictionary + MUST cells rather than a hand-kept list.
