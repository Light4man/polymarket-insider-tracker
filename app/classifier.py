from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from app.categories import detect_trade_categories
from app.models import AlertCandidate, TradeRecord, UserActivity


def is_rapid_reversal_activity(
    matched_activity: UserActivity,
    activities: list[UserActivity],
    *,
    window_seconds: int,
    max_usd_delta_ratio: Decimal,
    max_price_delta: Decimal,
    min_opposing_trades: int,
) -> bool:
    if matched_activity.usdc_size <= 0 or min_opposing_trades <= 0:
        return False

    opposing_matches = 0
    for activity in activities:
        if activity.transaction_hash == matched_activity.transaction_hash:
            continue
        if activity.side == matched_activity.side:
            continue
        if activity.condition_id != matched_activity.condition_id:
            continue
        if activity.asset != matched_activity.asset:
            continue
        if activity.outcome != matched_activity.outcome:
            continue
        if abs((activity.timestamp - matched_activity.timestamp).total_seconds()) > window_seconds:
            continue
        if abs(activity.price - matched_activity.price) > max_price_delta:
            continue

        usd_delta_ratio = (
            abs(activity.usdc_size - matched_activity.usdc_size)
            / matched_activity.usdc_size
        )
        if usd_delta_ratio <= max_usd_delta_ratio:
            opposing_matches += 1
            if opposing_matches >= min_opposing_trades:
                return True

    return False


def resolve_joined_at(
    profile_created_at: datetime | None,
    activities: list[UserActivity],
    *,
    fallback_trade_limit: int,
) -> datetime | None:
    if profile_created_at is not None:
        return profile_created_at
    if len(activities) < fallback_trade_limit and activities:
        return min(activity.timestamp for activity in activities)
    return None


def find_matching_activity(
    trade: TradeRecord,
    activities: list[UserActivity],
) -> UserActivity | None:
    exact_matches = [
        activity
        for activity in activities
        if activity.transaction_hash == trade.transaction_hash
        and activity.asset == trade.asset
        and activity.side == trade.side
    ]
    if exact_matches:
        return exact_matches[0]

    tx_matches = [
        activity
        for activity in activities
        if activity.transaction_hash == trade.transaction_hash
    ]
    return tx_matches[0] if tx_matches else None


def classify_trade(
    trade: TradeRecord,
    matched_activity: UserActivity,
    *,
    activities: list[UserActivity] | None = None,
    joined_at: datetime | None,
    executed_trade_count: int,
    outcome_price_max: Decimal,
    red_threshold_usd: Decimal,
    red_max_account_age_hours: int,
    red_max_executed_trades: int,
    yellow_threshold_usd: Decimal,
    yellow_max_account_age_days: int,
    yellow_max_executed_trades: int,
    yellow_excluded_categories: set[str] | frozenset[str],
    now: datetime,
    rapid_reversal_filter_enabled: bool = False,
    rapid_reversal_window_seconds: int = 600,
    rapid_reversal_max_usd_delta_ratio: Decimal = Decimal("0.05"),
    rapid_reversal_max_price_delta: Decimal = Decimal("0.03"),
    rapid_reversal_min_opposing_trades: int = 1,
) -> AlertCandidate | None:
    if joined_at is None:
        return None
    if trade.price > outcome_price_max:
        return None

    account_age = now - joined_at
    bet_size_usd = matched_activity.usdc_size
    categories = detect_trade_categories(trade)
    if categories.intersection(yellow_excluded_categories):
        return None
    if rapid_reversal_filter_enabled and activities is not None:
        if is_rapid_reversal_activity(
            matched_activity,
            activities,
            window_seconds=rapid_reversal_window_seconds,
            max_usd_delta_ratio=rapid_reversal_max_usd_delta_ratio,
            max_price_delta=rapid_reversal_max_price_delta,
            min_opposing_trades=rapid_reversal_min_opposing_trades,
        ):
            return None

    if (
        account_age < timedelta(hours=red_max_account_age_hours)
        and executed_trade_count < red_max_executed_trades
        and bet_size_usd >= red_threshold_usd
    ):
        return AlertCandidate(
            severity="RED",
            trade=trade,
            matched_activity=matched_activity,
            joined_at=joined_at,
            executed_trade_count=executed_trade_count,
            bet_size_usd=bet_size_usd,
        )

    if (
        account_age < timedelta(days=yellow_max_account_age_days)
        and executed_trade_count < yellow_max_executed_trades
        and bet_size_usd >= yellow_threshold_usd
    ):
        return AlertCandidate(
            severity="YELLOW",
            trade=trade,
            matched_activity=matched_activity,
            joined_at=joined_at,
            executed_trade_count=executed_trade_count,
            bet_size_usd=bet_size_usd,
        )

    return None
