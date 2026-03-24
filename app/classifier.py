from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from app.models import AlertCandidate, TradeRecord, UserActivity


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
    joined_at: datetime | None,
    executed_trade_count: int,
    outcome_price_max: Decimal,
    red_threshold_usd: Decimal,
    red_max_account_age_hours: int,
    red_max_executed_trades: int,
    yellow_threshold_usd: Decimal,
    yellow_max_account_age_days: int,
    yellow_max_executed_trades: int,
    now: datetime,
) -> AlertCandidate | None:
    if joined_at is None:
        return None
    if trade.price > outcome_price_max:
        return None

    account_age = now - joined_at
    bet_size_usd = matched_activity.usdc_size

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
