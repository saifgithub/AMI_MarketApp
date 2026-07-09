# CR / Defect definition of done

A short checklist the architect fills in per work item when submitting to the audit handshake
(`audit/handshake/`, CR005). Lives here rather than inline in the loop prompts so it can evolve
without editing `PROTOCOL.md` or the prompts. Every row gets a disposition: evidence, or `N/A`
with a one-line reason. A submission without this table filled in is incomplete.

| Row | Disposition |
|---|---|
| **Scope** — change matches the CR/DEF doc's stated Scope/Acceptance section | |
| **Tests** — `pytest backend/tests/unit/ -q` result (or `flutter analyze` / widget tests for mobile-only changes) | |
| **Manual verification** — how it was actually exercised (device build, `curl` against melehost, DB check) and the observed result | |
| **Docs** — `CLAUDE.md` / relevant `docs/` file updated if behaviour changed | |
| **Commit tag** — `(AT:R<N> CR###\|DEF###)` present on the commit(s) | |
| **Register** — `cr_list.md` / `def_list.md` row reflects the new status | |
| **Scope discipline** — no unrelated changes bundled into this commit | |

Not a replacement for the existing CR/Defect register process
([`docs/forward_planning/cr_list.md`](../forward_planning/cr_list.md),
[`docs/defect/def_list.md`](../defect/def_list.md)) — this table is the evidence an independent
auditor checks before calling an item COMPLETE.
