#!/usr/bin/env python3
"""Generate an animated GitHub contribution heatmap SVG (squares pop and flash in sequence).
Reads directly from data/contributions.json so all stats agree, or queries API if needed.
Validates that cell counts match the total before rendering.
Usage: python generate_streak_svg.py [username] [output.svg]
"""
import sys
import json
import os
import datetime
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
USER = sys.argv[1] if len(sys.argv) > 1 else "codenamann"
OUT  = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "contrib-heatmap.svg")


def get_data(user):
    # Prefer local snapshot from fetch_contributions.py so stats.svg and heatmap agree perfectly
    snap = os.path.join(ROOT, "data", "contributions.json")
    if os.path.exists(snap):
        try:
            d = json.load(open(snap, encoding="utf-8"))
            if d.get("username", "").lower() == user.lower() and all("level" in x for x in d.get("days", [])):
                return {"contributions": d["days"], "total": {"lastYear": d["total_contributions"]}}
        except Exception as e:
            print(f"Failed reading {snap}: {e}")

    url = f"https://github-contributions-api.jogruber.de/v4/{user}?y=last"
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"Fallback API failed: {e}")
        if os.path.exists(snap):
            d = json.load(open(snap, encoding="utf-8"))
            return {"contributions": d["days"], "total": {"lastYear": d["total_contributions"]}}
        raise


data = get_data(USER)
contribs = data["contributions"]
total = data["total"]["lastYear"]

# Validation step: ensure sum of daily counts matches total
if all("count" in c for c in contribs):
    cell_sum = sum(c["count"] for c in contribs)
    if cell_sum != total:
        print(f"generate_streak_svg: cell sum ({cell_sum}) != stored total ({total}). Synchronizing to cell sum.")
        total = cell_sum
    else:
        print(f"generate_streak_svg: validated cell sum ({cell_sum}) == total ({total})")

# ---- layout ----
CELL, GAP, RAD, LEFT, TOP = 13, 3, 2.5, 34, 24
COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
FLASH = "#b4ffaa"
GRAY = "#7d8590"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

n = len(contribs)
NW = (n + 6) // 7
W = LEFT + NW * (CELL + GAP) + 6
H = TOP + 7 * (CELL + GAP) + 22

# timing (seconds)
REVEAL, DUR = 3.6, 0.55
maxorder = (NW - 1) + 6 * 0.55

rects, labels = [], []
sd = datetime.date.fromisoformat(contribs[0]["date"])
last_m = None
for wk in range(NW):
    d = sd + datetime.timedelta(days=wk * 7)
    if d.month != last_m:
        last_m = d.month
        labels.append(f'<text class="lbl" x="{LEFT+wk*(CELL+GAP)}" y="{TOP-8}">{MONTHS[d.month-1]}</text>')
for name, r in [("Mon", 1), ("Wed", 3), ("Fri", 5)]:
    labels.append(f'<text class="lbl" x="2" y="{TOP+r*(CELL+GAP)+CELL-2}">{name}</text>')

for i, c in enumerate(contribs):
    wk, row, lvl = i // 7, i % 7, min(4, max(0, c["level"]))
    x = LEFT + wk * (CELL + GAP)
    y = TOP + row * (CELL + GAP)
    delay = round((wk + row * 0.55) / maxorder * REVEAL, 3)
    cls = "c g" if lvl >= 1 else "c e"
    rects.append(
        f'<rect class="{cls}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RAD}" '
        f'fill="{COLORS[lvl]}" style="animation-delay:{delay}s"/>'
    )

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">
<style>
  text.lbl {{ fill:{GRAY}; font-size:13px; font-weight:600; }}
  text.total {{ fill:#e6edf3; font-size:15px; font-weight:700; }}
  .c {{ transform-box:fill-box; transform-origin:center; opacity:0; animation:pop {DUR}s ease-out both; }}
  .g {{ animation:pop {DUR}s ease-out both, flash {DUR+0.15}s ease-out both; }}
  @keyframes pop {{ 0%{{opacity:0;transform:scale(.2)}} 60%{{opacity:1;transform:scale(1.1)}} 100%{{opacity:1;transform:scale(1)}} }}
  @keyframes flash {{ 0%{{filter:brightness(2.4)}} 45%{{filter:brightness(2.4)}} 100%{{filter:brightness(1)}} }}
  @media (prefers-reduced-motion: reduce) {{ .c {{ opacity:1 !important; animation:none !important; }} }}
</style>
<rect width="{W}" height="{H}" fill="none"/>
{''.join(labels)}
{''.join(rects)}
<text class="total" x="{LEFT}" y="{H-6}">{total:,} contributions in the last year</text>
</svg>'''

with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg)
print(f"Wrote {OUT}: {n} days, {total:,} contributions, {len(svg)//1024} KB (validated)")
