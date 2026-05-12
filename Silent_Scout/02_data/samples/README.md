# Data samples — what the SFT JSONL looks like

These are hand-crafted previews of one row per source per role. They show
shape, not real training content. The real training JSONL gets written to
`/raid/silent_scout/datasets/processed/<role>/train.jsonl` by the recipes
in `../recipes/`.

**Read these to understand:**
- How the **mandate overlay** is rendered into the **user side** of the prompt (not the system side).
- How the **base agent prompt** stays on the **system side**.
- How the **replay-mix** UltraChat rows look (no overlay, just generic instruction follow).

These files are commit-safe (no PII, no copyrighted dataset content).
