"""Generate the race-day QR code that points at the live dashboard.

Writes both an SVG (sharp at any size, used by qr.html) and a PNG (handy for
posters / Instagram). The URL comes from pipeline/config.py (SITE_URL), so the
QR always matches wherever the site is published.

    python scripts/make_qr.py

Re-run if you ever change SITE_URL. Safe to run anytime; it just overwrites the
two image files. Requires `segno` (in pipeline/requirements.txt).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

import segno  # noqa: E402
from config import SITE_URL  # noqa: E402

OUT_DIR = ROOT / "site" / "assets" / "img"
DARK = "#070b12"   # module colour (sits on the white card in qr.html)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    qr = segno.make(SITE_URL, error="h")  # high error-correction = scannable even if a corner is covered

    svg_path = OUT_DIR / "qr.svg"
    png_path = OUT_DIR / "qr.png"
    qr.save(str(svg_path), scale=10, border=2, dark=DARK, light=None)  # transparent background
    qr.save(str(png_path), scale=12, border=3, dark=DARK, light="#ffffff")

    print(f"QR target : {SITE_URL}")
    print(f"Wrote     : {svg_path}")
    print(f"Wrote     : {png_path}")


if __name__ == "__main__":
    main()
