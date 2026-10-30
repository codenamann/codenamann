from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "contributions.json"
OUT = ROOT / "contrib-heatmap.svg"

# GitHub contribution colors: Level 0 -> 4
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def main() -> None:
    if not DATA.exists():
        raise RuntimeError("data/contributions.json not found. Run scripts/fetch_contributions.py first.")

    payload = json.loads(DATA.read_text(encoding="utf-8"))
    days = payload.get("days", [])
    if not days:
        raise RuntimeError("No days found in data/contributions.json")

    first_dt = date.fromisoformat(days[0]["date"])
    # Sunday is index 0
    offset = (first_dt.weekday() + 1) % 7

    cell = 11
    gap = 3
    left = 48
    top = 58
    cols = (len(days) + offset + 6) // 7

    width = 860
    height = 200

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '  <title id="title">Codenaman GitHub Contributions</title>',
        '  <desc id="desc">Interactive animated contribution calendar auto-updated daily via GitHub Actions.</desc>',
        '  <style>',
        '    text { font-family: ui-monospace, SFMono-Regular, "Segoe UI", Menlo, Consolas, monospace; }',
        '    @keyframes appear {',
        '      0% { opacity: 0; transform: translateY(-4px); }',
        '      100% { opacity: 1; transform: translateY(0); }',
        '    }',
        '    .day {',
        '      opacity: 0;',
        '      animation: appear 0.28s ease-out forwards;',
        '    }',
        '    .day:hover {',
        '      stroke: #ffffff;',
        '      stroke-width: 1.5px;',
        '    }',
        '    @media (prefers-reduced-motion: reduce) {',
        '      .day { animation: none; opacity: 1; }',
        '    }',
        '  </style>',
        f'  <rect width="{width}" height="{height}" rx="10" fill="#0d1117" stroke="#30363d" stroke-width="1"/>',
        f'  <rect width="{width}" height="34" rx="10" fill="#161b22"/>',
        f'  <rect y="24" width="{width}" height="10" fill="#161b22"/>',
        '  <circle cx="20" cy="17" r="5" fill="#ff5f56"/>',
        '  <circle cx="38" cy="17" r="5" fill="#ffbd2e"/>',
        '  <circle cx="56" cy="17" r="5" fill="#27c93f"/>',
        f'  <text x="{width // 2}" y="21" text-anchor="middle" fill="#8b949e" font-size="11">codenamann@github ~ ./contributions.sh</text>',
    ]

    # Month labels calculation (ensuring at least 2 columns between labels)
    current_month = None
    last_month_col = -3
    for i, day in enumerate(days):
        day_date = date.fromisoformat(day["date"])
        month_label = day_date.strftime("%b")
        col = (i + offset) // 7
        if month_label != current_month and col < cols:
            if col - last_month_col >= 2:
                current_month = month_label
                last_month_col = col
                month_x = left + col * (cell + gap)
                parts.append(f'  <text x="{month_x}" y="{top - 8}" fill="#8b949e" font-size="9">{month_label}</text>')
            else:
                current_month = month_label

    # Day of week labels
    labels = [("Mon", 1), ("Wed", 3), ("Fri", 5)]
    for label, weekday in labels:
        label_y = top + weekday * (cell + gap) + 9
        parts.append(f'  <text x="18" y="{label_y}" fill="#8b949e" font-size="9">{label}</text>')

    # Grid of day squares
    for i, day in enumerate(days):
        col = (i + offset) // 7
        row = (i + offset) % 7
        x = left + col * (cell + gap)
        y = top + row * (cell + gap)
        level = max(0, min(4, int(day.get("level", 0))))
        color = PALETTE[level]

        # Diagonal stagger delay: (col + row) * factor
        delay = (col + row) * 0.015
        dt_str = day["date"]
        count = day.get("count", 0)
        c_text = f"{count} contribution" if count == 1 else f"{count} contributions"
        title = escape(f"{dt_str}: {c_text}")

        parts.append(
            f'  <rect class="day" style="animation-delay:{delay:.3f}s" '
            f'x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
            f'fill="{color}"><title>{title}</title></rect>'
        )

    # Footer section: Total count, streak, best day, and Less/More legend
    total = int(payload.get("total_contributions", 0))
    streak = int(payload.get("current_streak", 0))
    longest = int(payload.get("longest_streak", 0))
    footer_y = height - 16

    parts.append(
        f'  <text x="18" y="{footer_y}" fill="#c9d1d9" font-size="11" font-weight="500">'
        f'<tspan fill="#39d353">●</tspan> {total:,} contributions in past year  ·  '
        f'Streak: <tspan fill="#79c0ff">{streak} days</tspan> (max {longest}d)'
        f'</text>'
    )

    legend_x = width - 170
    parts.append(f'  <text x="{legend_x}" y="{footer_y}" fill="#8b949e" font-size="9">Less</text>')
    for i, color in enumerate(PALETTE):
        parts.append(f'  <rect x="{legend_x + 30 + i * 14}" y="{footer_y - 9}" width="10" height="10" rx="2" fill="{color}"/>')
    parts.append(f'  <text x="{legend_x + 106}" y="{footer_y}" fill="#8b949e" font-size="9">More</text>')

    parts.append("</svg>")

    OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"Rendered contribution heatmap SVG to {OUT}")


if __name__ == "__main__":
    main()
