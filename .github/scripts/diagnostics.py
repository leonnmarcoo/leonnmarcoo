#!/usr/bin/env python3
"""Render the Suit Diagnostics card for the profile README from live GitHub data."""

import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from xml.sax.saxutils import escape

USER = os.environ.get("GITHUB_REPOSITORY_OWNER", "leonnmarcoo")
API_URL = os.environ.get("GITHUB_API_URL", "https://api.github.com")
GRAPHQL_URL = os.environ.get("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql")
TOKEN = os.environ.get("GITHUB_TOKEN")

CALENDAR_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

BACKGROUND = "#0a0e14"
CYAN = "#6fe3ff"
GOLD = "#f2b233"
TEXT = "#f4f7fa"
MUTED = "#74838f"

STYLE = f"""
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }}
    .title {{ fill: {GOLD}; font-size: 15px; letter-spacing: 3px; }}
    .label {{ fill: {MUTED}; font-size: 13px; letter-spacing: 1px; }}
    .big {{ fill: {TEXT}; font-size: 40px; font-weight: 700; }}
    .value {{ fill: {TEXT}; font-size: 25px; font-weight: 700; }}
    .lang {{ fill: {TEXT}; font-size: 15px; }}
    .pulse {{ animation: pulse 2.4s ease-in-out infinite; }}
    @keyframes pulse {{ 50% {{ opacity: .3; }} }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
"""


def fetch(url, payload=None):
    headers = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = json.dumps(payload).encode() if payload else None
    request = urllib.request.Request(url, body, headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_calendar():
    result = fetch(GRAPHQL_URL, {"query": CALENDAR_QUERY, "variables": {"login": USER}})
    if "errors" in result:
        sys.exit(f"GraphQL error: {result['errors']}")
    return result["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def streaks(counts):
    """Return the (current, longest) runs of days with contributions."""
    longest = run = 0
    for count in counts:
        run = run + 1 if count else 0
        longest = max(longest, run)

    # Today isn't over yet, so an empty today doesn't end the current streak.
    current = 0
    for count in reversed(counts if counts[-1] else counts[:-1]):
        if not count:
            break
        current += 1
    return current, longest


def weekly_bars(weeks, x, bottom, width, height):
    totals = [sum(day["contributionCount"] for day in week["contributionDays"]) for week in weeks]
    peak = max(totals) or 1
    step = width / len(totals)
    bars = []
    for index, total in enumerate(totals):
        bar_height = max(total / peak * height, 2)
        color = GOLD if total == peak else CYAN
        opacity = 1 if total else 0.25
        bars.append(
            f'<rect x="{x + index * step:.1f}" y="{bottom - bar_height:.1f}" width="{step - 2:.1f}" '
            f'height="{bar_height:.1f}" rx="1" fill="{color}" fill-opacity="{opacity}"/>'
        )
    return "".join(bars)


def stat_tiles(stats, x, y, width):
    step = width / len(stats)
    tiles = []
    for index, (label, value) in enumerate(stats):
        left = x + index * step
        tiles.append(
            f'<text class="value" x="{left:.1f}" y="{y}">{escape(str(value))}</text>'
            f'<text class="label" x="{left:.1f}" y="{y + 22}">{escape(label)}</text>'
        )
    return "".join(tiles)


def power_cells(languages, x, y, width):
    """Draw one cell per repository for each of the most-used languages."""
    bar_x = x + 112
    bar_width = width - 112 - 30
    cell = bar_width / max(count for _, count in languages)
    rows = []
    for index, (language, count) in enumerate(languages):
        row_y = y + index * 28
        color = GOLD if index == 0 else CYAN
        cells = "".join(
            f'<rect x="{bar_x + n * cell:.1f}" y="{row_y - 12}" width="{cell - 3:.1f}" height="14" rx="1" fill="{color}"/>'
            for n in range(count)
        )
        rows.append(
            f'<text class="lang" x="{x}" y="{row_y}">{escape(language.replace(" Notebook", ""))}</text>{cells}'
            f'<text class="lang" x="{x + width}" y="{row_y}" text-anchor="end">{count}</text>'
        )
    return "".join(rows)


def render(profile, repos, calendar, today):
    counts = [day["contributionCount"] for week in calendar["weeks"] for day in week["contributionDays"]]
    current, longest = streaks(counts)
    languages = Counter(repo["language"] for repo in repos if repo["language"]).most_common(6)
    stats = [
        ("STREAK", current or "IDLE"),
        ("BEST RUN", longest),
        ("ACTIVE", sum(1 for count in counts if count)),
        ("REPOS", len(repos)),
        ("STARS", sum(repo["stargazers_count"] for repo in repos)),
        ("FOLLOWERS", profile["followers"]),
    ]
    total = calendar["totalContributions"]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 300" width="900" height="300" role="img" aria-labelledby="title">
  <title id="title">Suit diagnostics for {escape(USER)}: {total} contributions in the last 12 months</title>
  <defs>
    <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
      <path d="M30 0H0V30" fill="none" stroke="{CYAN}" stroke-opacity=".07"/>
    </pattern>
  </defs>
  <style>{STYLE}  </style>
  <rect width="900" height="300" rx="14" fill="{BACKGROUND}"/>
  <rect width="900" height="300" rx="14" fill="url(#grid)"/>
  <path d="M14 44V14H44M856 14H886V44M886 256V286H856M44 286H14V256" fill="none" stroke="{CYAN}" stroke-opacity=".5" stroke-width="2"/>

  <text class="title" x="36" y="50">SUIT DIAGNOSTICS</text>
  <circle class="pulse" cx="600" cy="45" r="5" fill="{CYAN}"/>
  <text class="label" x="864" y="50" text-anchor="end">ONLINE // SCANNED {today}</text>

  <text class="big" x="36" y="108">{total}</text>
  <text class="label" x="{36 + len(str(total)) * 24 + 12}" y="92">CONTRIBUTIONS</text>
  <text class="label" x="{36 + len(str(total)) * 24 + 12}" y="108">LAST 12 MONTHS</text>
  {weekly_bars(calendar["weeks"], 36, 196, 524, 72)}
  {stat_tiles(stats, 36, 240, 524)}

  <path d="M584 72V262" stroke="{CYAN}" stroke-opacity=".3"/>
  <text class="label" x="606" y="88">POWER CELLS // 1 PER REPO</text>
  {power_cells(languages, 606, 122, 258)}
</svg>
"""


def main():
    profile = fetch(f"{API_URL}/users/{USER}")
    repos = [repo for repo in fetch(f"{API_URL}/users/{USER}/repos?per_page=100&type=owner") if not repo["fork"]]
    today = datetime.now(timezone.utc).date().isoformat()
    svg = render(profile, repos, fetch_calendar(), today)

    output = sys.argv[1]
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as file:
        file.write(svg)


if __name__ == "__main__":
    main()
