from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.classifier import classify_trade, resolve_joined_at
from app.models import TradeRecord, UserActivity


def build_trade() -> TradeRecord:
    return TradeRecord(
        proxy_wallet="0xabc",
        side="BUY",
        asset="asset-1",
        condition_id="condition-1",
        size=Decimal("100"),
        price=Decimal("0.5"),
        timestamp=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
        title="Test Market",
        slug="test-market",
        outcome="Yes",
        transaction_hash="0xtx",
    )


def build_activity(
    *,
    timestamp: datetime,
    usdc_size: str,
    tx_hash: str = "0xtx",
) -> UserActivity:
    return UserActivity(
        proxy_wallet="0xabc",
        timestamp=timestamp,
        condition_id="condition-1",
        trade_type="TRADE",
        size=Decimal("100"),
        usdc_size=Decimal(usdc_size),
        transaction_hash=tx_hash,
        price=Decimal("0.5"),
        asset="asset-1",
        side="BUY",
        outcome="Yes",
        title="Test Market",
        slug="test-market",
    )


def test_red_alert_boundary() -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    trade = build_trade()
    activity = build_activity(timestamp=now - timedelta(minutes=10), usdc_size="9950")

    candidate = classify_trade(
        trade,
        activity,
        joined_at=now - timedelta(hours=23, minutes=59),
        executed_trade_count=2,
        outcome_price_max=Decimal("0.95"),
        red_threshold_usd=Decimal("9950"),
        red_max_account_age_hours=24,
        red_max_executed_trades=3,
        yellow_threshold_usd=Decimal("4949"),
        yellow_max_account_age_days=10,
        yellow_max_executed_trades=10,
        yellow_excluded_categories=frozenset(),
        now=now,
    )

    assert candidate is not None
    assert candidate.severity == "RED"


def test_yellow_alert_boundary() -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    trade = build_trade()
    activity = build_activity(timestamp=now - timedelta(minutes=10), usdc_size="4949")

    candidate = classify_trade(
        trade,
        activity,
        joined_at=now - timedelta(days=9, hours=23),
        executed_trade_count=9,
        outcome_price_max=Decimal("0.95"),
        red_threshold_usd=Decimal("9950"),
        red_max_account_age_hours=24,
        red_max_executed_trades=3,
        yellow_threshold_usd=Decimal("4949"),
        yellow_max_account_age_days=10,
        yellow_max_executed_trades=10,
        yellow_excluded_categories=frozenset(),
        now=now,
    )

    assert candidate is not None
    assert candidate.severity == "YELLOW"


def test_exact_yellow_age_cutoff_does_not_alert() -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    trade = build_trade()
    activity = build_activity(timestamp=now - timedelta(minutes=10), usdc_size="20000")

    candidate = classify_trade(
        trade,
        activity,
        joined_at=now - timedelta(days=10),
        executed_trade_count=1,
        outcome_price_max=Decimal("0.95"),
        red_threshold_usd=Decimal("9950"),
        red_max_account_age_hours=24,
        red_max_executed_trades=3,
        yellow_threshold_usd=Decimal("4949"),
        yellow_max_account_age_days=10,
        yellow_max_executed_trades=10,
        yellow_excluded_categories=frozenset(),
        now=now,
    )

    assert candidate is None


def test_resolve_joined_at_uses_profile_when_available() -> None:
    profile_created_at = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)
    activities = [
        build_activity(timestamp=datetime(2026, 3, 22, 10, 0, tzinfo=UTC), usdc_size="100"),
        build_activity(timestamp=datetime(2026, 3, 21, 8, 0, tzinfo=UTC), usdc_size="120", tx_hash="0xtx2"),
    ]

    joined_at = resolve_joined_at(
        profile_created_at,
        activities,
        fallback_trade_limit=10,
    )

    assert joined_at == profile_created_at


def test_resolve_joined_at_falls_back_to_oldest_activity_when_under_limit() -> None:
    activities = [
        build_activity(timestamp=datetime(2026, 3, 22, 10, 0, tzinfo=UTC), usdc_size="100"),
        build_activity(timestamp=datetime(2026, 3, 21, 8, 0, tzinfo=UTC), usdc_size="120", tx_hash="0xtx2"),
    ]

    joined_at = resolve_joined_at(None, activities, fallback_trade_limit=10)

    assert joined_at == datetime(2026, 3, 21, 8, 0, tzinfo=UTC)


def test_resolve_joined_at_returns_none_when_activity_limit_hit() -> None:
    activities = [
        build_activity(
            timestamp=datetime(2026, 3, 22, 10, 0, tzinfo=UTC) - timedelta(minutes=index),
            usdc_size="100",
            tx_hash=f"0xtx{index}",
        )
        for index in range(10)
    ]

    assert resolve_joined_at(None, activities, fallback_trade_limit=10) is None


def test_resolve_joined_at_uses_custom_fallback_limit() -> None:
    activities = [
        build_activity(
            timestamp=datetime(2026, 3, 22, 10, 0, tzinfo=UTC) - timedelta(minutes=index),
            usdc_size="100",
            tx_hash=f"0xtx{index}",
        )
        for index in range(12)
    ]

    joined_at = resolve_joined_at(None, activities, fallback_trade_limit=15)

    assert joined_at == min(activity.timestamp for activity in activities)


def test_outcome_price_above_limit_does_not_alert() -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    trade = TradeRecord(
        proxy_wallet="0xabc",
        side="BUY",
        asset="asset-1",
        condition_id="condition-1",
        size=Decimal("100"),
        price=Decimal("0.951"),
        timestamp=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
        title="Test Market",
        slug="test-market",
        outcome="Yes",
        transaction_hash="0xtx",
    )
    activity = build_activity(timestamp=now - timedelta(minutes=10), usdc_size="4949")

    candidate = classify_trade(
        trade,
        activity,
        joined_at=now - timedelta(days=2),
        executed_trade_count=2,
        outcome_price_max=Decimal("0.95"),
        red_threshold_usd=Decimal("9950"),
        red_max_account_age_hours=24,
        red_max_executed_trades=3,
        yellow_threshold_usd=Decimal("4949"),
        yellow_max_account_age_days=10,
        yellow_max_executed_trades=10,
        yellow_excluded_categories=frozenset(),
        now=now,
    )

    assert candidate is None


def test_outcome_price_equal_to_limit_still_alerts() -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    trade = TradeRecord(
        proxy_wallet="0xabc",
        side="BUY",
        asset="asset-1",
        condition_id="condition-1",
        size=Decimal("100"),
        price=Decimal("0.95"),
        timestamp=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
        title="Test Market",
        slug="test-market",
        outcome="Yes",
        transaction_hash="0xtx",
    )
    activity = build_activity(timestamp=now - timedelta(minutes=10), usdc_size="4949")

    candidate = classify_trade(
        trade,
        activity,
        joined_at=now - timedelta(days=2),
        executed_trade_count=2,
        outcome_price_max=Decimal("0.95"),
        red_threshold_usd=Decimal("9950"),
        red_max_account_age_hours=24,
        red_max_executed_trades=3,
        yellow_threshold_usd=Decimal("4949"),
        yellow_max_account_age_days=10,
        yellow_max_executed_trades=10,
        yellow_excluded_categories=frozenset(),
        now=now,
    )

    assert candidate is not None


def test_yellow_sport_trade_can_be_excluded_by_category() -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    trade = TradeRecord(
        proxy_wallet="0xabc",
        side="BUY",
        asset="asset-1",
        condition_id="condition-1",
        size=Decimal("100"),
        price=Decimal("0.5"),
        timestamp=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
        title="McCabe vs. Matsuoka: Match O/U 21.5",
        slug="atp-mccabe-matsuok-2026-03-25",
        outcome="Over",
        transaction_hash="0xtx",
        event_slug="atp-mccabe-matsuok-2026-03-25",
    )
    activity = build_activity(timestamp=now - timedelta(minutes=10), usdc_size="5000")

    candidate = classify_trade(
        trade,
        activity,
        joined_at=now - timedelta(days=2),
        executed_trade_count=1,
        outcome_price_max=Decimal("0.95"),
        red_threshold_usd=Decimal("9950"),
        red_max_account_age_hours=24,
        red_max_executed_trades=3,
        yellow_threshold_usd=Decimal("4949"),
        yellow_max_account_age_days=10,
        yellow_max_executed_trades=10,
        yellow_excluded_categories=frozenset({"sport"}),
        now=now,
    )

    assert candidate is None


def test_red_sport_trade_is_not_blocked_by_yellow_category_filter() -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    trade = TradeRecord(
        proxy_wallet="0xabc",
        side="BUY",
        asset="asset-1",
        condition_id="condition-1",
        size=Decimal("100"),
        price=Decimal("0.5"),
        timestamp=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
        title="McCabe vs. Matsuoka: Match O/U 21.5",
        slug="atp-mccabe-matsuok-2026-03-25",
        outcome="Over",
        transaction_hash="0xtx",
        event_slug="atp-mccabe-matsuok-2026-03-25",
    )
    activity = build_activity(timestamp=now - timedelta(minutes=10), usdc_size="12000")

    candidate = classify_trade(
        trade,
        activity,
        joined_at=now - timedelta(hours=6),
        executed_trade_count=1,
        outcome_price_max=Decimal("0.95"),
        red_threshold_usd=Decimal("9950"),
        red_max_account_age_hours=24,
        red_max_executed_trades=3,
        yellow_threshold_usd=Decimal("4949"),
        yellow_max_account_age_days=10,
        yellow_max_executed_trades=10,
        yellow_excluded_categories=frozenset({"sport"}),
        now=now,
    )

    assert candidate is not None
    assert candidate.severity == "RED"
