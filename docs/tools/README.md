# Tools

Reusable, standing capabilities that don't belong to a single CR/Defect/RES
item — built once during a specific investigation, kept here so the next one
doesn't start from scratch. Distinct from `docs/Research/`: a RES folder is a
finding with a beginning and an end; a folder here is a tool meant to be
picked back up.

**Nothing here touches production code.** Same rule as `docs/Research/` —
these are diagnostic/investigation scripts, not part of the shipped app.

## Index

| Folder | What it's for |
|---|---|
| [`room_investigation/`](room_investigation/) | Rerun the Room (single agent or the full 12-agent convene), on Kimi or vLLM, N times, to check consistency; trace a verdict back through `llm_audit`. Built during CR228/RES009 (2026-09). |
