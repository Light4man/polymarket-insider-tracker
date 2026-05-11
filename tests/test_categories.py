from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.categories import detect_trade_categories
from app.models import TradeRecord


def build_trade(*, title: str, slug: str = "test-market") -> TradeRecord:
    return TradeRecord(
        proxy_wallet="0xabc",
        side="BUY",
        asset="asset-1",
        condition_id="condition-1",
        size=Decimal("100"),
        price=Decimal("0.5"),
        timestamp=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
        title=title,
        slug=slug,
        outcome="Yes",
        transaction_hash="0xtx",
    )


def test_detects_sport_title_with_vs_dot() -> None:
    trade = build_trade(title="Arsenal FC vs. Club Atletico de Madrid")

    assert "sport" in detect_trade_categories(trade)


def test_detects_sport_title_with_vs_without_dot() -> None:
    trade = build_trade(
        title="Indian Premier League: Royal Challengers Bangalore vs Mumbai Indians",
        slug="cricipl-roy-mum-2026-05-10",
    )

    assert "sport" in detect_trade_categories(trade)


def test_detects_sport_title_with_fc_or_cf_token() -> None:
    fc_trade = build_trade(title="Will Real Madrid FC win on 2026-05-10?")
    cf_trade = build_trade(title="Will Valencia CF win on 2026-05-10?")

    assert "sport" in detect_trade_categories(fc_trade)
    assert "sport" in detect_trade_categories(cf_trade)


def test_detects_sport_spread_market() -> None:
    trade = build_trade(
        title="Spread: Galatasaray SK (-1.5)",
        slug="tur-gal-ant-2026-05-09-more-markets",
    )

    assert "sport" in detect_trade_categories(trade)


def test_detects_champions_league_market() -> None:
    trade = build_trade(
        title="Will PSG win the 2025-26 Champions League?",
        slug="uefa-champions-league-winner",
    )

    assert "sport" in detect_trade_categories(trade)
