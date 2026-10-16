# ruff: noqa: E501
"""Publish the curated briefing plates as tracked documentation assets (a versioned snapshot).

  outputs/briefing/maps/*.png                       reproducible build output (git-ignored), from make_plates.py
  docs/product/hearthmap-briefing-v0.1/assets/*.png published documentation snapshot (tracked)

Only the presentation-approved plates in PUBLISHED are copied. A plate under the repository hygiene limit (1 MB) is copied
byte-identical; a larger one is re-encoded as a 256-colour palette PNG at the same pixel size (max-coverage palette, no
dithering) and refused if any pixel channel moves by more than MAX_CHANNEL_ERROR, so legend colours stay faithful.

Usage:  python scripts/briefing/publish_plates.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "outputs/briefing/maps"
ASSETS = ROOT / "docs/product/hearthmap-briefing-v0.1/assets"
MAX_BYTES = 1_000_000
MAX_CHANNEL_ERROR = 12  # of 255
PUBLISHED = (
    "00-hearthmap-overview",
    "01-hazard-foundation",
    "02-routing-accessibility",
    "03-education-healthcare",
    "04-settlement-built-form",
    "05-town-services",
    "05b-town-services-sensitivity",
    "06-industry-mining-context",
    "07-evidence-state",
    "08-future-product-concept",
)


def main() -> int:
    missing = [n for n in PUBLISHED if not (BUILD / f"{n}.png").exists()]
    if missing:
        print("missing build plates (run scripts/briefing/make_plates.py first):", missing)
        return 1
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name in PUBLISHED:
        src, dst = BUILD / f"{name}.png", ASSETS / f"{name}.png"
        how = "copied"
        if src.stat().st_size <= MAX_BYTES:
            shutil.copyfile(src, dst)
        else:
            with Image.open(src) as im:
                rgb = im.convert("RGB")
                pal = rgb.quantize(
                    colors=256, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE
                )
                err = int(np.abs(np.asarray(pal.convert("RGB"), int) - np.asarray(rgb, int)).max())
                if err > MAX_CHANNEL_ERROR:
                    print(f"{name}: palette colour error {err} > {MAX_CHANNEL_ERROR}")
                    return 1
                pal.save(dst, optimize=True)
                how = f"palette-encoded, max channel error {err}/255"
        size = dst.stat().st_size
        if size > MAX_BYTES:
            print(f"{dst.name}: {size:,} bytes exceeds {MAX_BYTES:,}")
            return 1
        print(f"published {dst.relative_to(ROOT)} ({size / 1e6:.2f} MB, {how})")
    stray = sorted(p.name for p in ASSETS.glob("*.png") if p.stem not in PUBLISHED)
    if stray:
        print("unexpected files in assets (not curated):", stray)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
