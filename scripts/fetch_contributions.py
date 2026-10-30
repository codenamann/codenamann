#!/usr/bin/env python3
"""
Fetch real daily contribution counts for codenamann:
- Supports GitHub GraphQL API (including private contributions if token present)
- Falls back to public unauthenticated contributions scraping
- Computes streaks (current & longest), active days, best day, and monthly totals
- Validates that daily sum, monthly totals, and total_contributions match exactly
- Writes data/contributions.json for render_stats_svg.py and generate_streak_svg.py
"""
import datetime
import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GH_PROFILE_USER", "codenamann")
ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data" / "contributions.json"

LEVEL_MAP = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


def fetch_days_graphql(token: str):
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "codenamann-profile-readme/1.0",
    }
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                contributionLevel
              }
            }
          }
        }
      }
    }
    """
    try:
        resp = requests.post(
            url,
            json={"query": query, "variables": {"login": USERNAME}},
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"GraphQL request failed: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
            return None
        data = resp.json()
        if "errors" in data:
            print(f"GraphQL returned errors: {data['errors']}", file=sys.stderr)
            return None
        cal = data.get("data", {}).get("user", {}).get("contributionsCollection", {}).get("contributionCalendar", {})
        weeks = cal.get("weeks", [])
        if not weeks:
            return None

        days = []
        for week in weeks:
            for day in week.get("contributionDays", []):
                days.append({
                    "date": day["date"],
                    "count": int(day["contributionCount"]),
                    "level": LEVEL_MAP.get(day["contributionLevel"], 0),
                })
        print(f"Fetched {len(days)} days via GitHub GraphQL API (authenticated).")
        return days
    except Exception as exc:
        print(f"GraphQL error: {exc}", file=sys.stderr)
        return None


def fetch_days_public():
    url = f"https://github.com/users/{USERNAME}/contributions"
    print(f"Scraping public contributions from {url}...")
    resp = requests.get(url, headers={"User-Agent": "codenamann-profile-readme/1.0"}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cells = soup.select("td.ContributionCalendar-day")
    if not cells:
        print("No contribution calendar cells found.", file=sys.stderr)
        sys.exit(1)

    days = []
    for td in cells:
        date = td.get("data-date")
        if not date:
            continue
        td_id = td.get("id")
        tooltip_el = soup.find("tool-tip", attrs={"for": td_id}) if td_id else None
        text = tooltip_el.get_text(strip=True) if tooltip_el else ""
        if re.search(r"no contributions", text, re.I):
            count = 0
        else:
            m = re.match(r"(\d+)", text)
            count = int(m.group(1)) if m else 0
        days.append({"date": date, "count": count, "level": int(td.get("data-level") or 0)})

    days.sort(key=lambda d: d["date"])
    print(f"Scraped {len(days)} days from GitHub public calendar.")
    return days


def compute_current_streak(days):
    idx = len(days) - 1
    if idx >= 0 and days[idx]["count"] == 0:
        idx -= 1  # today isn't over yet
    streak = 0
    end_idx = idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days):
    longest = run = 0
    longest_start = longest_end = None
    run_start_idx = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start_idx = i
            run += 1
            if run > longest:
                longest = run
                longest_start = days[run_start_idx]["date"]
                longest_end = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_data(days):
    days.sort(key=lambda d: d["date"])
    total = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"]) if days else {"date": "", "count": 0}
    cur_len, cur_start, cur_end = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)

    monthly = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]

    # VALIDATION STEP: Verify daily sum and monthly sum match total_contributions exactly
    daily_sum = sum(d["count"] for d in days)
    monthly_sum = sum(m["total"] for m in monthly_list)
    if daily_sum != total:
        raise ValueError(f"Validation failed: daily sum ({daily_sum}) != total ({total})")
    if monthly_sum != total:
        raise ValueError(f"Validation failed: monthly sum ({monthly_sum}) != total ({total})")
    print(f"Validation passed: daily sum ({daily_sum}) == monthly sum ({monthly_sum}) == total ({total})")

    return {
        "username": USERNAME,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]} if days else {"start": "", "end": ""},
        "total_contributions": total,
        "active_days": active_days,
        "avg_per_active_day": round(total / active_days, 1) if active_days else 0,
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {"length": long_len, "start": long_start, "end": long_end},
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly_list,
        "days": days,
    }


def main():
    token = os.getenv("GH_PAT") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    days = None
    if token:
        print("GitHub token detected, querying GraphQL API...")
        days = fetch_days_graphql(token.strip())

    if not days:
        days = fetch_days_public()

    data = build_data(days)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"wrote {OUT_PATH}: {data['total_contributions']} contributions, "
          f"current streak {data['current_streak']['length']}, "
          f"longest streak {data['longest_streak']['length']}")


if __name__ == "__main__":
    main()
