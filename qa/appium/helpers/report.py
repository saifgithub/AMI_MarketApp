"""Evidence + summary output. See README.md "Output" for the shape this
produces under $AMI_REPORT_DIR."""

from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image, ImageDraw


class FlagCollector:
    """Findings accumulate here across the whole session; conftest's
    pytest_sessionfinish writes them out once, so a mechanical check can
    *record* a finding without failing the test it runs in — a UAT pass wants
    the full report, not a stop on the first flagged screen."""

    def __init__(self) -> None:
        self.findings: list[dict] = []
        self._next_id = 1

    def add(self, finding: dict) -> dict:
        finding = {"id": f"F{self._next_id:03d}", **finding}
        self._next_id += 1
        self.findings.append(finding)
        return finding


def annotate_png(
    png_bytes: bytes,
    out_path: Path,
    *,
    navbar_top_y: int | None = None,
    boxes: list[tuple[int, int, int, int]] | None = None,
) -> None:
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    width, _height = image.size
    if navbar_top_y is not None:
        draw.rectangle([0, navbar_top_y, width, image.size[1]], fill=(255, 0, 0, 60))
    for x1, y1, x2, y2 in boxes or []:
        draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0, 255), width=4)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)


def write_summary_json(
    out_path: Path,
    *,
    run_id: str,
    device_meta: dict,
    app_version: str,
    findings: list[dict],
    passes: int,
    skips: int,
) -> None:
    summary = {
        "run_id": run_id,
        "device": device_meta,
        "app_version": app_version,
        "findings": findings,
        "passes": passes,
        "skips": skips,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
