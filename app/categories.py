from __future__ import annotations

import re

from app.models import TradeRecord


SPORTS_LEAGUE_PREFIXES = {
    "afl",
    "atp",
    "bundesliga",
    "champions-league",
    "cricipl",
    "cs2",
    "epl",
    "europa-league",
    "f1",
    "la-liga",
    "ligue-1",
    "lol",
    "mlb",
    "mma",
    "nba",
    "ncaab",
    "ncaaf",
    "nfl",
    "nhl",
    "serie-a",
    "tennis",
    "ufc",
    "uefa-champions-league",
    "valorant",
    "wnba",
    "wta",
}

SPORTS_TITLE_MARKERS = (
    "fifa",
    "world cup",
    "champions league",
    "indian premier league",
    "cricket",
    "match o/u",
    "match winner",
    "map ",
    "spread:",
    "(bo",
    "counter-strike",
    "esports",
    "ipl",
    "atp",
    "wta",
    "ufc",
    "mma",
    "nba",
    "nfl",
    "nhl",
    "mlb",
    "serie a",
    "la liga",
    "bundesliga",
    "ligue 1",
)

SPORTS_TITLE_PATTERNS = (
    re.compile(r"\bvs\.?\b"),
    re.compile(r"\bfc\b"),
    re.compile(r"\bcf\b"),
)


def detect_trade_categories(trade: TradeRecord) -> set[str]:
    categories: set[str] = set()
    slug_candidates = [trade.slug.lower()]
    if trade.event_slug:
        slug_candidates.append(trade.event_slug.lower())

    for slug in slug_candidates:
        for prefix in SPORTS_LEAGUE_PREFIXES:
            if slug.startswith(f"{prefix}-"):
                categories.add("sport")
                break

    title = trade.title.lower()
    if any(marker in title for marker in SPORTS_TITLE_MARKERS):
        categories.add("sport")
    if any(pattern.search(title) for pattern in SPORTS_TITLE_PATTERNS):
        categories.add("sport")

    return categories
