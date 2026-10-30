from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USERNAME = "codenamann"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "contributions.json"

LEVEL_MAP = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


def fetch_contributions_graphql(token: str) -> list[dict] | None:
    """Fetch all contributions (including private if token has repo scope) via GitHub GraphQL API."""
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
        response = requests.post(
            url,
            json={"query": query, "variables": {"login": USERNAME}},
            headers=headers,
            timeout=30,
        )
        if response.status_code != 200:
            print(f"GraphQL request failed with status {response.status_code}: {response.text[:200]}")
            return None

        data = response.json()
        if "errors" in data:
            print(f"GraphQL returned errors: {data['errors']}")
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
                    "level": LEVEL_MAP.get(day["contributionLevel"], 0),
                    "count": int(day["contributionCount"]),
                })
        print(f"Successfully fetched {len(days)} days via GitHub GraphQL API (private repos included with authorized token).")
        return days
    except Exception as exc:
        print(f"GraphQL fetch encountered an error: {exc}. Falling back to public scraper.")
        return None


def fetch_contributions_public() -> list[dict]:
    """Fetch public contributions calendar (which also includes private activity if enabled in GitHub profile settings)."""
    url = f"https://github.com/users/{USERNAME}/contributions"
    print(f"Fetching public contribution calendar from {url}...")
    response = requests.get(
        url,
        headers={"User-Agent": "codenamann-profile-readme/1.0 (Mozilla/5.0)"},
        timeout=30,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Map tooltip texts by target cell id
    tooltips: dict[str, str] = {}
    for tt in soup.find_all("tool-tip", attrs={"for": True}):
        target_id = tt.get("for")
        if target_id:
            tooltips[target_id] = tt.get_text().strip()

    days = []
    for cell in soup.select("td.ContributionCalendar-day"):
        date_str = cell.get("data-date")
        if not date_str:
            continue

        raw_level = cell.get("data-level", "0")
        try:
            level = max(0, min(4, int(raw_level)))
        except ValueError:
            level = 0

        cell_id = cell.get("id", "")
        label = tooltips.get(cell_id, "") or cell.get("aria-label", "") or ""
        match = re.search(r"([\d,]+)\s+contributions?", label, re.I)
        count = int(match.group(1).replace(",", "")) if match else (level if level > 0 else 0)
        days.append({"date": date_str, "level": level, "count": count})

    if not days:
        raise RuntimeError("No contribution day cells were found in GitHub HTML.")

    return days


def main() -> None:
    token = os.getenv("GH_PAT") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    days = None
    if token:
        print("GitHub token detected. Attempting to fetch via GraphQL API (includes private contributions)...")
        days = fetch_contributions_graphql(token.strip())

    if not days:
        days = fetch_contributions_public()

    days.sort(key=lambda day: day["date"])
    counts = [day["count"] for day in days]
    active = [day for day in days if day["count"] > 0]
    best_day = max(days, key=lambda day: day["count"]) if days else {"date": "", "count": 0}
    total = sum(counts)

    # Compute current streak
    current_streak = 0
    today = datetime.now(timezone.utc).date()
    by_date = {day["date"]: day for day in days}
    cursor = today
    if cursor.isoformat() not in by_date or by_date[cursor.isoformat()]["count"] == 0:
        cursor -= timedelta(days=1)

    while cursor.isoformat() in by_date and by_date[cursor.isoformat()]["count"] > 0:
        current_streak += 1
        cursor -= timedelta(days=1)

    longest_streak = 0
    running = 0
    previous = None
    for day in days:
        date_val = datetime.strptime(day["date"], "%Y-%m-%d").date()
        if day["count"] > 0:
            running = running + 1 if previous and (date_val - previous).days == 1 else 1
            longest_streak = max(longest_streak, running)
            previous = date_val
        else:
            running = 0
            previous = date_val

    month_totals = Counter()
    for day in days:
        month_totals[day["date"][:7]] += day["count"]

    payload = {
        "username": USERNAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_contributions": total,
        "active_days": len(active),
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "best_day": {"date": best_day["date"], "count": best_day["count"]},
        "monthly_totals": dict(sorted(month_totals.items())),
        "days": days,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(days)} days, {total:,} contributions, {current_streak}d streak to {OUT}")


if __name__ == "__main__":
    main()
