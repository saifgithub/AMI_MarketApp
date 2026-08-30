#!/usr/bin/env python3
"""Pull a YouTube video's metadata + auto-caption transcript into readable text.

Exists because YouTube's `timedtext` endpoint returns 0 bytes without a session
token, the innertube fallback 400s, and the public transcript mirrors sit behind
Cloudflare JS challenges — so `yt-dlp` (which solves the player challenge) is the
only reliable fetch path. Raw auto-caption VTT is also unreadable: it repeats
every line 2-3x as the rolling caption redraws. This deduplicates and merges into
timestamped blocks so the transcript can be read in `sed -n` chunks.

Writes `meta.txt` + `transcript.txt` and prints their paths.
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


def require_yt_dlp() -> str:
    exe = shutil.which("yt-dlp")
    if not exe:
        sys.exit(
            "yt-dlp not found. Install it once, globally:\n"
            "    brew install yt-dlp"
        )
    return exe


def fetch(url: str, out_dir: str, lang: str) -> tuple[dict, str]:
    """Return (metadata dict, path to the best .vtt) — downloads no video."""
    os.makedirs(out_dir, exist_ok=True)
    exe = require_yt_dlp()

    meta_raw = subprocess.run(
        [exe, "--dump-json", "--skip-download", url],
        capture_output=True, text=True, timeout=180,
    )
    if meta_raw.returncode != 0:
        sys.exit(f"yt-dlp could not read the video:\n{meta_raw.stderr.strip()[:800]}")
    meta = json.loads(meta_raw.stdout)

    sub = subprocess.run(
        [exe, "--write-auto-subs", "--write-subs", "--sub-lang", f"{lang}.*",
         "--skip-download", "--sub-format", "vtt/best",
         "-o", os.path.join(out_dir, "%(id)s"), url],
        capture_output=True, text=True, timeout=300,
    )
    vtts = sorted(f for f in os.listdir(out_dir) if f.endswith(".vtt"))
    if not vtts:
        sys.exit(
            f"No {lang} captions available for this video.\n"
            f"{sub.stderr.strip()[:500]}"
        )
    # Prefer the manually-authored track (`.<lang>.vtt`) over ASR (`.<lang>-orig.vtt`).
    best = next((v for v in vtts if "-orig" not in v), vtts[0])
    return meta, os.path.join(out_dir, best)


def to_blocks(vtt_path: str, block_secs: int) -> list[tuple[int, str]]:
    """Dedupe the rolling-caption repeats, merge into ~block_secs chunks."""
    cues: list[tuple[int, str]] = []
    seen: set[str] = set()
    ts = 0
    for line in open(vtt_path, encoding="utf-8", errors="ignore"):
        stamp = re.match(r"^(\d\d):(\d\d):(\d\d)\.\d+ -->", line)
        if stamp:
            h, m, s = map(int, stamp.groups())
            ts = h * 3600 + m * 60 + s
            continue
        text = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
        if not text or text.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if text in seen:
            continue
        seen.add(text)
        cues.append((ts, text))

    blocks: list[tuple[int, str]] = []
    buf: list[str] = []
    start = None
    for ts, text in cues:
        if start is None:
            start = ts
        if ts - start >= block_secs and buf:
            blocks.append((start, " ".join(buf)))
            buf, start = [], ts
        buf.append(text)
    if buf:
        blocks.append((start or 0, " ".join(buf)))
    return blocks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url", help="YouTube URL or bare video ID")
    ap.add_argument("--out-dir", help="where to write (default: a temp dir)")
    ap.add_argument("--lang", default="en", help="caption language prefix (default: en)")
    ap.add_argument("--block-secs", type=int, default=30,
                    help="seconds of speech per timestamped block (default: 30)")
    args = ap.parse_args()

    url = args.url
    if re.fullmatch(r"[\w-]{11}", url):
        url = f"https://www.youtube.com/watch?v={url}"

    out_dir = args.out_dir or tempfile.mkdtemp(prefix="yt-extract-")
    meta, vtt = fetch(url, out_dir, args.lang)
    blocks = to_blocks(vtt, args.block_secs)

    secs = int(meta.get("duration") or 0)
    meta_lines = [
        f"title:       {meta.get('title')}",
        f"channel:     {meta.get('uploader')}  ({meta.get('channel_url')})",
        f"published:   {meta.get('upload_date')}",
        f"duration:    {secs // 60}m{secs % 60:02d}s",
        f"views:       {meta.get('view_count')}",
        f"url:         {meta.get('webpage_url')}",
        "",
        "--- chapters ---",
    ]
    for ch in (meta.get("chapters") or []):
        t = int(ch.get("start_time") or 0)
        meta_lines.append(f"[{t // 60:02d}:{t % 60:02d}] {ch.get('title')}")
    if not meta.get("chapters"):
        meta_lines.append("(none)")
    meta_lines += ["", "--- description ---", meta.get("description") or "(none)"]

    meta_path = os.path.join(out_dir, "meta.txt")
    txt_path = os.path.join(out_dir, "transcript.txt")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("\n".join(meta_lines) + "\n")
    with open(txt_path, "w", encoding="utf-8") as f:
        for start, text in blocks:
            f.write(f"[{start // 60:02d}:{start % 60:02d}] {text}\n")

    print(f"meta:       {meta_path}")
    print(f"transcript: {txt_path}")
    print(f"blocks:     {len(blocks)}  (~{args.block_secs}s each, {secs // 60}m video)")


if __name__ == "__main__":
    main()
