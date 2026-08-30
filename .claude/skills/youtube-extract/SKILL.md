---
name: youtube-extract
description: Pull a YouTube video's transcript and metadata, then review it for what actually transfers to AMI Trade. Use when the user shares a YouTube link, asks to review/summarise/extract a video or talk, or asks what we can learn from one.
---

# youtube-extract

Turn a YouTube link into a readable transcript, then review it against what this
repo already ships. The review half matters more than the fetch half.

## 1. Fetch

```bash
python3 .claude/skills/youtube-extract/scripts/fetch_transcript.py <url-or-id> \
    --out-dir <your session scratchpad>
```

Writes `meta.txt` (title, channel, date, duration, chapters, full description) and
`transcript.txt` (deduplicated, `[mm:ss]`-stamped ~30s blocks). Accepts a bare video
ID or any watch URL, `&t=` included. `--lang` for non-English, `--block-secs` to
change block size.

Needs `yt-dlp` once: `brew install yt-dlp`. Don't hand-roll a fetch — YouTube's
`timedtext` endpoint returns 0 bytes without a session token, the innertube fallback
400s, and the public transcript mirrors are behind Cloudflare.

## 2. Read

**`meta.txt` first, before a word of transcript.** Who published this and what do they
sell? A prop firm, a broker, a course vendor and a researcher produce very different
documents, and knowing which you're holding changes how every claim reads. Check the
description for ad reads and affiliate links.

Then read `transcript.txt` in chunks — `sed -n '1,40p'`, `sed -n '41,80p'` — not in one
gulp. A 60-minute video is ~110 blocks.

## 3. Review

Long videos are usually two or three different videos welded together. Segment by
value before judging the whole, and say where the seam is.

For each segment worth keeping:

- **Check what we already ship before recommending anything.** Grep `content/lessons/`,
  `docs/forward_planning/cr_list.md`, `docs/defect/def_list.md`, `backend/app/services/`.
  Re-proposing shipped work as a discovery is the main failure mode here.
- **Sort every idea into three bins, explicitly:** transfers as-is · transfers in *shape*
  only (the mechanism generalises, the data doesn't) · needs data or infrastructure we
  don't have. Name which bin, don't blur them.
- **Judge the mechanism separately from the medium.** A futures scalper's entry rule may
  be useless at our instrument and horizon and still carry a decision grammar worth
  taking. Dismissing on medium alone is how you miss the transferable half.
- **Never repeat a self-reported performance number as fact.** Win rates, returns,
  Sharpe, "I made 100% in a month" — no sample size, no audit, selected on survival.
  Report them as claims, with the window, or leave them out.
- **Separate what the speaker demonstrates from what they assert.** A drawn-out,
  falsifiable process is evidence about the process. A story about mindset is not.

## 4. If it leads to a change

Governance applies as normal: a CR for planned work, a DEF for something broken vs
spec. Educational content lifted from a video needs a real source under CR060 —
a trader's anecdote is a hypothesis, not a citation. Any EN lesson edit flags AR/MS
re-translation.

Keep the transcript in the scratchpad. It doesn't belong in the repo.
