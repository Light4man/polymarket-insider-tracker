from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.models import AlertCandidate, SummaryRow, TradeRecord, UserActivity
from app.summary import format_alert_message, format_summary_message


def build_candidate(severity: str = "YELLOW") -> AlertCandidate:
    trade = TradeRecord(
        proxy_wallet="0x4bc2ed22a07b83d3052d98c5d96d042b7ce6f01b",
        side="BUY",
        asset="asset-1",
        condition_id="condition-1",
        size=Decimal("4250"),
        price=Decimal("0.341"),
        timestamp=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
        title="LoL: Bilibili Gaming vs JD Gaming - Game 3 Winner",
        slug="lol-blg-vs-jdg-game-3",
        outcome="JD Gaming",
        transaction_hash="0xa991a745907b53fea8481b913f7e16faf9269082c65346d5aa3d4ed420bfe262",
    )
    activity = UserActivity(
        proxy_wallet=trade.proxy_wallet,
        timestamp=trade.timestamp,
        condition_id=trade.condition_id,
        trade_type="TRADE",
        size=trade.size,
        usdc_size=Decimal("1450"),
        transaction_hash=trade.transaction_hash,
        price=trade.price,
        asset=trade.asset,
        side=trade.side,
        outcome=trade.outcome,
        title=trade.title,
        slug=trade.slug,
    )
    return AlertCandidate(
        severity=severity,
        trade=trade,
        matched_activity=activity,
        joined_at=datetime(2026, 3, 13, 8, 0, tzinfo=UTC),
        executed_trade_count=4,
        bet_size_usd=Decimal("1450"),
    )


def test_format_alert_message_contains_links_and_fields() -> None:
    message = format_alert_message(build_candidate())

    assert "Suspicious Activity" in message
    assert '<b>Market:</b> <a href="https://polymarket.com/event/lol-blg-vs-jdg-game-3">' in message
    assert "<b>Side:</b> BUY" in message
    assert "<b>Outcome:</b> JD Gaming @ $0.341" in message
    assert "<b>Bet Size:</b> $1,450 USD" in message
    assert "Joined 2026-03-13" in message
    assert "<b>Wallet:</b> <code>0x4bc2ed22a07b83d3052d98c5d96d042b7ce6f01b</code>" in message
    assert "polygonscan.com/tx/" in message
    assert "polymarket.com/" in message


def test_format_alert_message_uses_sports_event_url_when_available() -> None:
    candidate = build_candidate()
    trade = TradeRecord(
        proxy_wallet=candidate.trade.proxy_wallet,
        side=candidate.trade.side,
        asset=candidate.trade.asset,
        condition_id=candidate.trade.condition_id,
        size=candidate.trade.size,
        price=Decimal("0.39"),
        timestamp=candidate.trade.timestamp,
        title="Will Newcastle United FC win on 2026-03-22?",
        slug="epl-new-sun-2026-03-22-new",
        outcome="No",
        transaction_hash=candidate.trade.transaction_hash,
        event_slug="epl-new-sun-2026-03-22",
    )
    candidate = AlertCandidate(
        severity=candidate.severity,
        trade=trade,
        matched_activity=candidate.matched_activity,
        joined_at=candidate.joined_at,
        executed_trade_count=candidate.executed_trade_count,
        bet_size_usd=candidate.bet_size_usd,
    )

    message = format_alert_message(candidate)

    assert (
        '<b>Market:</b> <a href="https://polymarket.com/sports/epl/epl-new-sun-2026-03-22">'
        in message
    )


def test_format_summary_message_renders_top_table() -> None:
    rows = [
        SummaryRow("Counter-Strike: PARIVISION vs Team Spirit", Decimal("53876")),
        SummaryRow("US x Iran ceasefire by April 30?", Decimal("39869")),
    ]

    message = format_summary_message(rows, top_n=10)

    assert "24h Whale Summary" in message
    assert "<pre>" in message
    assert "$53,876" in message
    assert "Counter-Strike" in message


def test_format_summary_message_handles_empty_rows() -> None:
    message = format_summary_message([], top_n=10)

    assert "No alert-triggered whale trades" in message


def test_format_alert_message_rounds_float_artifact_price() -> None:
    candidate = build_candidate()
    trade = TradeRecord(
        proxy_wallet=candidate.trade.proxy_wallet,
        side=candidate.trade.side,
        asset=candidate.trade.asset,
        condition_id=candidate.trade.condition_id,
        size=candidate.trade.size,
        price=Decimal("0.2899999999756151"),
        timestamp=candidate.trade.timestamp,
        title=candidate.trade.title,
        slug=candidate.trade.slug,
        outcome="G2 Esports",
        transaction_hash=candidate.trade.transaction_hash,
    )
    candidate = AlertCandidate(
        severity=candidate.severity,
        trade=trade,
        matched_activity=candidate.matched_activity,
        joined_at=candidate.joined_at,
        executed_trade_count=candidate.executed_trade_count,
        bet_size_usd=candidate.bet_size_usd,
    )

    message = format_alert_message(candidate)

    assert "<b>Outcome:</b> G2 Esports @ $0.29" in message


def test_format_alert_message_shows_sell_side() -> None:
    candidate = build_candidate()
    trade = TradeRecord(
        proxy_wallet=candidate.trade.proxy_wallet,
        side="SELL",
        asset=candidate.trade.asset,
        condition_id=candidate.trade.condition_id,
        size=candidate.trade.size,
        price=Decimal("0.95"),
        timestamp=candidate.trade.timestamp,
        title="Will China invade Taiwan by June 30, 2026?",
        slug="will-china-invade-taiwan-by-june-30-2026",
        outcome="No",
        transaction_hash=candidate.trade.transaction_hash,
    )
    activity = UserActivity(
        proxy_wallet=trade.proxy_wallet,
        timestamp=trade.timestamp,
        condition_id=trade.condition_id,
        trade_type="TRADE",
        size=trade.size,
        usdc_size=Decimal("5940.85"),
        transaction_hash=trade.transaction_hash,
        price=trade.price,
        asset=trade.asset,
        side="SELL",
        outcome=trade.outcome,
        title=trade.title,
        slug=trade.slug,
    )
    candidate = AlertCandidate(
        severity="YELLOW",
        trade=trade,
        matched_activity=activity,
        joined_at=candidate.joined_at,
        executed_trade_count=7,
        bet_size_usd=Decimal("5940.85"),
    )

    message = format_alert_message(candidate)

    assert "<b>Side:</b> SELL" in message
