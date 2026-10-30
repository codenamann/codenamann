from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source-prepped.png"
OUT = ROOT / "codenamann-ascii.svg"

RAMP = " .`:-=+*cs#%@"
COLS = 84
ROWS = 52


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit("Run scripts/prep_photo.py first to create data/source-prepped.png")

    img = Image.open(SOURCE).convert("RGBA")
    arr = np.array(img)
    gray = arr[:, :, 0]
    alpha = arr[:, :, 3]

    resized_gray = cv2.resize(gray, (COLS, ROWS), interpolation=cv2.INTER_AREA)
    resized_alpha = cv2.resize(alpha, (COLS, ROWS), interpolation=cv2.INTER_AREA)
    is_subject = resized_alpha > 25

    width = 370
    height = 454
    char_w = 4.22
    row_h = 7.15
    start_x = (width - int(COLS * char_w)) // 2 + 3
    start_y = 46

    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '  <title id="title">Animated ASCII Portrait of Codenaman</title>',
        '  <desc id="desc">High-definition terminal ASCII art portrait auto-typing on load.</desc>',
        '  <style>',
        '    text { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; }',
        '    .ascii { font-size: 8.4px; font-weight: 600; fill: #c9d1d9; letter-spacing: -0.15px; }',
        '    .row { opacity: 0; animation: type 0.1s steps(1, end) forwards; }',
        '    @keyframes type { to { opacity: 1; } }',
        '    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }',
        '    .cursor { animation: blink 0.9s infinite; }',
        '    @media (prefers-reduced-motion: reduce) {',
        '      .row { animation: none; opacity: 1; }',
        '      .cursor { animation: none; opacity: 1; }',
        '    }',
        '  </style>',
        f'  <rect width="{width}" height="{height}" rx="10" fill="#0d1117" stroke="#30363d" stroke-width="1"/>',
        f'  <rect width="{width}" height="34" rx="10" fill="#161b22"/>',
        f'  <rect y="24" width="{width}" height="10" fill="#161b22"/>',
        '  <circle cx="20" cy="17" r="5" fill="#ff5f56"/>',
        '  <circle cx="38" cy="17" r="5" fill="#ffbd2e"/>',
        '  <circle cx="56" cy="17" r="5" fill="#27c93f"/>',
        f'  <text x="{width // 2}" y="21" text-anchor="middle" fill="#8b949e" font-size="11">codenamann — portrait.ascii</text>',
    ]

    for y in range(ROWS):
        chars = []
        for x in range(COLS):
            if not is_subject[y, x]:
                chars.append(" ")
            else:
                val = int(resized_gray[y, x])
                # Map subject tone: 20..240 -> 1..12
                idx = int((240 - val) / 220.0 * (len(RAMP) - 2)) + 1
                chars.append(RAMP[max(1, min(len(RAMP) - 1, idx))])

        line = "".join(chars).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        delay = y * 0.02
        y_pos = start_y + (y + 1) * row_h
        pieces.append(
            f'  <text class="row ascii" style="animation-delay:{delay:.2f}s" '
            f'x="{start_x}" y="{y_pos:.1f}" xml:space="preserve">{line}</text>'
        )

    pieces.append(
        '  <text x="20" y="434" fill="#39d353" font-size="11" font-weight="600">'
        '$ whoami<tspan class="cursor" fill="#39d353"> █</tspan></text>'
    )
    pieces.append("</svg>")

    OUT.write_text("\n".join(pieces) + "\n", encoding="utf-8")
    print(f"Generated solid high-definition ASCII portrait SVG to {OUT}")


if __name__ == "__main__":
    main()
