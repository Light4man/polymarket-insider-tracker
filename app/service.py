from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.classifier import classify_trade, find_matching_activity, resolve_joined_at
from app.models import TradeRecord
from app.polymarket import PolymarketClient
from app.settings import Settings
from app.storage import Storage
from app.summary import format_alert_message, format_summary_message
from app.telegram import TelegramClient

TIMEZONE_ALIASES = {
    "Europe/Kiev": "Europe/Kyiv",
}


def resolve_timezone_name(name: str) -> str:
    return TIMEZONE_ALIASES.get(name, name)


class TrackerService:
    def __init__(
        self,
        settings: Settings,
        polymarket_client: PolymarketClient,
        telegram_client: TelegramClient,
        storage: Storage,
    ) -> None:
        self.settings = settings
        self.polymarket_client = polymarket_client
        self.telegram_client = telegram_client
        self.storage = storage
        self.logger = logging.getLogger(__name__)
        timezone_name = resolve_timezone_name(settings.summary_timezone)
        try:
            self.summary_zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                "Invalid SUMMARY_TIMEZONE. "
                f"Got '{settings.summary_timezone}', resolved to '{timezone_name}'. "
                "Install tzdata or use a valid IANA zone like 'Europe/Kyiv' or 'UTC'."
            ) from exc

    async def run(self) -> None:
        self.storage.initialize()

        while True:
            now = datetime.now(tz=UTC)
            try:
                await self.poll_once(now=now)
                await self.maybe_send_daily_summary(now=now)
            except Exception:
                self.logger.exception("Tracker loop failed")
            await asyncio.sleep(self.settings.poll_interval_seconds)

    async def poll_once(self, *, now: datetime) -> None:
        trades = await self.polymarket_client.fetch_recent_trades(
            self.settings.yellow_threshold_usd,
            limit=100,
            taker_only=False,
        )
        batch_seen: set[str] = set()

        for trade in sorted(trades, key=lambda item: item.timestamp):
            if trade.dedupe_key in batch_seen or self.storage.has_seen_trade(
                trade.dedupe_key
            ):
                continue

            processed = await self._process_trade(trade, now=now)
            if processed:
                self.storage.mark_trade_seen(
                    trade.dedupe_key,
                    transaction_hash=trade.transaction_hash,
                    wallet=trade.proxy_wallet,
                    seen_at=now,
                )
                batch_seen.add(trade.dedupe_key)

    async def _process_trade(self, trade: TradeRecord, *, now: datetime) -> bool:
        activity_limit = max(
            self.settings.red_max_executed_trades,
            self.settings.yellow_max_executed_trades,
        )
        activities = await self.polymarket_client.fetch_user_activity(
            trade.proxy_wallet,
            limit=activity_limit,
        )
        matched_activity = find_matching_activity(trade, activities)
        if matched_activity is None:
            self.logger.warning(
                "No matching activity found for wallet=%s tx=%s",
                trade.proxy_wallet,
                trade.transaction_hash,
            )
            return False

        profile_created_at = await self._get_profile_created_at(
            trade.proxy_wallet,
            now=now,
        )
        joined_at = resolve_joined_at(
            profile_created_at,
            activities,
            fallback_trade_limit=activity_limit,
        )

        candidate = classify_trade(
            trade,
            matched_activity,
            joined_at=joined_at,
            executed_trade_count=len(activities),
            outcome_price_max=self.settings.outcome_price_max,
            red_threshold_usd=self.settings.red_threshold_usd,
            red_max_account_age_hours=self.settings.red_max_account_age_hours,
            red_max_executed_trades=self.settings.red_max_executed_trades,
            yellow_threshold_usd=self.settings.yellow_threshold_usd,
            yellow_max_account_age_days=self.settings.yellow_max_account_age_days,
            yellow_max_executed_trades=self.settings.yellow_max_executed_trades,
            yellow_excluded_categories=self.settings.yellow_excluded_categories,
            now=now,
        )
        if candidate is None:
            return True

        message = format_alert_message(candidate)
        await self.telegram_client.send_message(
            self.settings.telegram_alert_chat_id,
            message,
        )
        self.storage.record_alert(candidate, alerted_at=now)
        self.logger.info(
            "Sent %s alert for wallet=%s tx=%s usd=%s",
            candidate.severity,
            trade.proxy_wallet,
            trade.transaction_hash,
            candidate.bet_size_usd,
        )
        return True

    async def _get_profile_created_at(
        self,
        wallet: str,
        *,
        now: datetime,
    ) -> datetime | None:
        cached, created_at = self.storage.get_cached_profile(wallet)
        if cached:
            return created_at

        profile = await self.polymarket_client.fetch_public_profile(wallet)
        created_at = profile.created_at if profile else None
        self.storage.upsert_wallet_profile(
            wallet,
            created_at=created_at,
            fetched_at=now,
        )
        return created_at

    async def maybe_send_daily_summary(self, *, now: datetime) -> bool:
        local_now = now.astimezone(self.summary_zone)
        summary_date = local_now.date().isoformat()
        scheduled_time = datetime.combine(
            local_now.date(),
            self.settings.summary_time,
            tzinfo=self.summary_zone,
        )

        if local_now < scheduled_time:
            return False
        if self.storage.summary_already_sent(summary_date):
            return False

        rows = self.storage.get_summary_market_totals(
            since=now - timedelta(hours=24),
            limit=self.settings.summary_top_n,
        )
        message = format_summary_message(rows, top_n=self.settings.summary_top_n)
        await self.telegram_client.send_message(
            self.settings.telegram_summary_chat_id,
            message,
        )
        self.storage.mark_summary_sent(summary_date, sent_at=now)
        self.logger.info("Sent daily summary for %s", summary_date)
        return True
