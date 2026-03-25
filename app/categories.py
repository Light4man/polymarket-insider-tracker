from __future__ import annotations

from app.models import TradeRecord


SPORTS_LEAGUE_PREFIXES = {
    "afl",
    "atp",
    "bundesliga",
    "champions-league",
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
    "valorant",
    "wnba",
    "wta",
}

SPORTS_TITLE_MARKERS = (
    "fifa",
    "world cup",
    "match o/u",
    "match winner",
    "map ",
    "(bo",
    "counter-strike",
    "esports",
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

    return categories
