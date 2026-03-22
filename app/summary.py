from __future__ import annotations

from html import escape

from app.models import AlertCandidate, SummaryRow


SPORTS_LEAGUE_PREFIXES = {
    "afl",
    "bundesliga",
    "champions-league",
    "epl",
    "europa-league",
    "f1",
    "la-liga",
    "ligue-1",
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
    "wnba",
}


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _format_price(value) -> str:
    normalized = format(value.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized


def _build_market_url(candidate: AlertCandidate) -> str:
    event_slug = candidate.trade.event_slug
    if event_slug:
        for league in sorted(SPORTS_LEAGUE_PREFIXES, key=len, reverse=True):
            prefix = f"{league}-"
            if event_slug.startswith(prefix):
                return f"https://polymarket.com/sports/{league}/{event_slug}"
        return f"https://polymarket.com/event/{event_slug}"
    return f"https://polymarket.com/event/{candidate.trade.slug}"


def format_alert_message(candidate: AlertCandidate) -> str:
    title = escape(candidate.trade.title)
    outcome = escape(candidate.trade.outcome)
    price = _format_price(candidate.trade.price)
    bet_size = f"{candidate.bet_size_usd:,.0f}"
    joined_date = candidate.joined_at.date().isoformat()
    tx_url = f"https://polygonscan.com/tx/{candidate.trade.transaction_hash}"
    market_url = _build_market_url(candidate)
    profile_url = (
        "https://polymarket.com/"
        f"@{candidate.trade.proxy_wallet}?via=alertbot"
    )

    header = {
        "RED": "🚨 [High Risk]",
        "YELLOW": "⚠️ [Suspicious Activity]",
    }[candidate.severity]

    lines = [
        f"<b>{escape(header)}</b>",
        f'<b>Market:</b> <a href="{escape(market_url)}">{title}</a>',
        f"<b>Outcome:</b> {outcome} @ ${price}",
        f"<b>Bet Size:</b> ${bet_size} USD",
        f"<b>Account:</b> Joined {joined_date}",
        f"<b>Wallet:</b> <code>{escape(candidate.trade.proxy_wallet)}</code>",
        f"<b>Trade Count:</b> {candidate.executed_trade_count}",
        f'<a href="{escape(tx_url)}">View Transaction</a>',
        f'<a href="{escape(profile_url)}">View Profile</a>',
    ]
    return "\n".join(lines)


def format_summary_message(rows: list[SummaryRow], *, top_n: int) -> str:
    if not rows:
        return "📊 24h Whale Summary\nNo alert-triggered whale trades in the last 24 hours."

    market_width = 30
    header = f"📊 24h Whale Summary (Top {top_n} Markets)"
    table_lines = [
        f"{'Market':<{market_width}} | Total USD",
        "-" * (market_width + 12),
    ]
    for row in rows:
        market = _truncate(escape(row.market_title), market_width)
        total = f"${row.total_usd:,.0f}"
        table_lines.append(f"{market:<{market_width}} | {total}")
    return header + "\n<pre>" + "\n".join(table_lines) + "</pre>"
