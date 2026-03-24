from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.models import PublicProfile, TradeRecord, UserActivity
from app.service import TrackerService, resolve_timezone_name
from app.settings import Settings
from app.storage import Storage


class FakePolymarketClient:
    def __init__(
        self,
        trades: list[TradeRecord],
        activities: dict[str, list[UserActivity]],
        profiles: dict[str, PublicProfile | None],
    ) -> None:
        self.trades = trades
        self.activities = activities
        self.profiles = profiles
        self.activity_limits: list[int] = []

    async def fetch_recent_trades(
        self,
        min_usd: str,
        *,
        limit: int = 100,
        taker_only: bool = False,
    ) -> list[TradeRecord]:
        return list(self.trades)

    async def fetch_user_activity(
        self,
        wallet: str,
        *,
        limit: int = 10,
    ) -> list[UserActivity]:
        self.activity_limits.append(limit)
        return list(self.activities[wallet])

    async def fetch_public_profile(self, wallet: str) -> PublicProfile | None:
        return self.profiles.get(wallet)


class FakeTelegramClient:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    async def send_message(self, chat_id: str, text: str) -> None:
        self.messages.append((chat_id, text))


def build_settings(sqlite_path: Path) -> Settings:
    return Settings(
        telegram_bot_token="token",
        telegram_alert_chat_id="@alerts",
        telegram_summary_chat_id="@summary",
        outcome_price_max=Decimal("0.95"),
        red_threshold_usd=Decimal("9950"),
        red_max_account_age_hours=24,
        red_max_executed_trades=3,
        yellow_threshold_usd=Decimal("4949"),
        yellow_max_account_age_days=10,
        yellow_max_executed_trades=10,
        poll_interval_seconds=5,
        summary_time=datetime.strptime("23:55", "%H:%M").time(),
        summary_timezone="UTC",
        summary_top_n=10,
        sqlite_path=sqlite_path,
        log_level="INFO",
    )


def build_trade(
    *,
    wallet: str,
    tx_hash: str,
    side: str = "BUY",
    asset: str = "asset-1",
    price: str = "0.5",
    title: str = "Will NVIDIA reach $244 in March?",
    slug: str = "will-nvda-reach-244-in-march",
    timestamp: datetime | None = None,
) -> TradeRecord:
    return TradeRecord(
        proxy_wallet=wallet,
        side=side,
        asset=asset,
        condition_id="condition-1",
        size=Decimal("10000"),
        price=Decimal(price),
        timestamp=timestamp or datetime(2026, 3, 22, 12, 0, tzinfo=UTC),
        title=title,
        slug=slug,
        outcome="No",
        transaction_hash=tx_hash,
    )


def build_activity(
    *,
    wallet: str,
    tx_hash: str,
    usdc_size: str,
    timestamp: datetime,
    side: str = "BUY",
    asset: str = "asset-1",
    title: str = "Will NVIDIA reach $244 in March?",
    slug: str = "will-nvda-reach-244-in-march",
) -> UserActivity:
    return UserActivity(
        proxy_wallet=wallet,
        timestamp=timestamp,
        condition_id="condition-1",
        trade_type="TRADE",
        size=Decimal("10000"),
        usdc_size=Decimal(usdc_size),
        transaction_hash=tx_hash,
        price=Decimal("0.993"),
        asset=asset,
        side=side,
        outcome="No",
        title=title,
        slug=slug,
    )


def test_service_sends_red_and_dedupes_repeated_poll(tmp_path: Path) -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    wallet = "0xred"
    trade = build_trade(wallet=wallet, tx_hash="0xtx-red")
    activities = {
        wallet: [
            build_activity(wallet=wallet, tx_hash="0xtx-red", usdc_size="11993.72", timestamp=now),
            build_activity(wallet=wallet, tx_hash="0xolder", usdc_size="50", timestamp=now),
        ]
    }
    profiles = {wallet: PublicProfile(proxy_wallet=wallet, created_at=now)}
    storage = Storage(tmp_path / "tracker.db")
    storage.initialize()
    telegram = FakeTelegramClient()
    service = TrackerService(
        settings=build_settings(tmp_path / "tracker.db"),
        polymarket_client=FakePolymarketClient([trade], activities, profiles),
        telegram_client=telegram,
        storage=storage,
    )

    asyncio.run(service.poll_once(now=now))
    asyncio.run(service.poll_once(now=now))

    assert len(telegram.messages) == 1
    assert "[High Risk]" in telegram.messages[0][1]
    assert "<b>Wallet:</b> <code>0xred</code>" in telegram.messages[0][1]
    count = storage.connection.execute("SELECT COUNT(*) FROM sent_alerts").fetchone()[0]
    assert count == 1


def test_service_sends_yellow_with_activity_fallback_joined_at(tmp_path: Path) -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    wallet = "0xyellow"
    trade = build_trade(wallet=wallet, tx_hash="0xtx-yellow")
    activities = {
        wallet: [
            build_activity(
                wallet=wallet,
                tx_hash="0xtx-yellow",
                usdc_size="6000",
                timestamp=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
            ),
            build_activity(
                wallet=wallet,
                tx_hash="0xolder",
                usdc_size="100",
                timestamp=datetime(2026, 3, 15, 10, 0, tzinfo=UTC),
            ),
        ]
    }
    profiles = {wallet: None}
    storage = Storage(tmp_path / "tracker.db")
    storage.initialize()
    telegram = FakeTelegramClient()
    service = TrackerService(
        settings=build_settings(tmp_path / "tracker.db"),
        polymarket_client=FakePolymarketClient([trade], activities, profiles),
        telegram_client=telegram,
        storage=storage,
    )

    asyncio.run(service.poll_once(now=now))

    assert len(telegram.messages) == 1
    assert "[Suspicious Activity]" in telegram.messages[0][1]
    assert "Joined 2026-03-15" in telegram.messages[0][1]


def test_service_skips_wallet_with_ten_or_more_trades(tmp_path: Path) -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    wallet = "0xbusy"
    trade = build_trade(wallet=wallet, tx_hash="0xtx-0")
    activities = {
        wallet: [
            build_activity(
                wallet=wallet,
                tx_hash=f"0xtx-{index}",
                usdc_size="7000" if index == 0 else "10",
                timestamp=now,
            )
            for index in range(10)
        ]
    }
    profiles = {
        wallet: PublicProfile(
            proxy_wallet=wallet,
            created_at=datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
        )
    }
    storage = Storage(tmp_path / "tracker.db")
    storage.initialize()
    telegram = FakeTelegramClient()
    service = TrackerService(
        settings=build_settings(tmp_path / "tracker.db"),
        polymarket_client=FakePolymarketClient([trade], activities, profiles),
        telegram_client=telegram,
        storage=storage,
    )

    asyncio.run(service.poll_once(now=now))

    assert telegram.messages == []


def test_same_transaction_with_different_wallets_is_processed_separately(tmp_path: Path) -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    wallet_a = "0xwalleta"
    wallet_b = "0xwalletb"
    trade_a = build_trade(wallet=wallet_a, tx_hash="0xsame", asset="asset-a")
    trade_b = build_trade(wallet=wallet_b, tx_hash="0xsame", asset="asset-b")
    activities = {
        wallet_a: [
            build_activity(wallet=wallet_a, tx_hash="0xsame", usdc_size="6000", timestamp=now, asset="asset-a"),
        ],
        wallet_b: [
            build_activity(wallet=wallet_b, tx_hash="0xsame", usdc_size="12000", timestamp=now, asset="asset-b"),
        ],
    }
    profiles = {
        wallet_a: PublicProfile(proxy_wallet=wallet_a, created_at=datetime(2026, 3, 20, 12, 0, tzinfo=UTC)),
        wallet_b: PublicProfile(proxy_wallet=wallet_b, created_at=now),
    }
    storage = Storage(tmp_path / "tracker.db")
    storage.initialize()
    telegram = FakeTelegramClient()
    service = TrackerService(
        settings=build_settings(tmp_path / "tracker.db"),
        polymarket_client=FakePolymarketClient([trade_a, trade_b], activities, profiles),
        telegram_client=telegram,
        storage=storage,
    )

    asyncio.run(service.poll_once(now=now))

    assert len(telegram.messages) == 2


def test_daily_summary_uses_last_24_hours_and_sorts_descending(tmp_path: Path) -> None:
    now = datetime(2026, 3, 22, 23, 56, tzinfo=UTC)
    storage = Storage(tmp_path / "tracker.db")
    storage.initialize()
    storage.connection.executemany(
        """
        INSERT INTO sent_alerts
        (dedupe_key, severity, wallet, transaction_hash, market_title, market_slug, usd_size, alerted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("a", "YELLOW", "0x1", "0xa", "Market B", "market-b", "6000", "2026-03-22T22:00:00+00:00"),
            ("b", "RED", "0x2", "0xb", "Market A", "market-a", "12000", "2026-03-22T21:00:00+00:00"),
            ("c", "YELLOW", "0x3", "0xc", "Market B", "market-b", "5000", "2026-03-22T20:00:00+00:00"),
            ("d", "YELLOW", "0x4", "0xd", "Old Market", "old-market", "9000", "2026-03-20T10:00:00+00:00"),
        ],
    )
    storage.connection.commit()
    telegram = FakeTelegramClient()
    service = TrackerService(
        settings=build_settings(tmp_path / "tracker.db"),
        polymarket_client=FakePolymarketClient([], {}, {}),
        telegram_client=telegram,
        storage=storage,
    )

    sent = asyncio.run(service.maybe_send_daily_summary(now=now))

    assert sent is True
    assert len(telegram.messages) == 1
    assert "Market B" in telegram.messages[0][1]
    assert "Market A" in telegram.messages[0][1]
    assert telegram.messages[0][1].find("Market A") < telegram.messages[0][1].find("Market B")


def test_resolve_timezone_name_maps_kiev_to_kyiv() -> None:
    assert resolve_timezone_name("Europe/Kiev") == "Europe/Kyiv"
    assert resolve_timezone_name("UTC") == "UTC"


def test_service_uses_configured_activity_limit(tmp_path: Path) -> None:
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    wallet = "0xlimit"
    trade = build_trade(wallet=wallet, tx_hash="0xtx-limit")
    activities = {
        wallet: [
            build_activity(wallet=wallet, tx_hash="0xtx-limit", usdc_size="6000", timestamp=now),
        ]
    }
    profiles = {
        wallet: PublicProfile(
            proxy_wallet=wallet,
            created_at=datetime(2026, 3, 22, 8, 0, tzinfo=UTC),
        )
    }
    settings = build_settings(tmp_path / "tracker.db")
    settings = Settings(
        telegram_bot_token=settings.telegram_bot_token,
        telegram_alert_chat_id=settings.telegram_alert_chat_id,
        telegram_summary_chat_id=settings.telegram_summary_chat_id,
        outcome_price_max=settings.outcome_price_max,
        red_threshold_usd=settings.red_threshold_usd,
        red_max_account_age_hours=settings.red_max_account_age_hours,
        red_max_executed_trades=5,
        yellow_threshold_usd=settings.yellow_threshold_usd,
        yellow_max_account_age_days=settings.yellow_max_account_age_days,
        yellow_max_executed_trades=12,
        poll_interval_seconds=settings.poll_interval_seconds,
        summary_time=settings.summary_time,
        summary_timezone=settings.summary_timezone,
        summary_top_n=settings.summary_top_n,
        sqlite_path=settings.sqlite_path,
        log_level=settings.log_level,
    )
    storage = Storage(tmp_path / "tracker.db")
    storage.initialize()
    telegram = FakeTelegramClient()
    polymarket = FakePolymarketClient([trade], activities, profiles)
    service = TrackerService(
        settings=settings,
        polymarket_client=polymarket,
        telegram_client=telegram,
        storage=storage,
    )

    asyncio.run(service.poll_once(now=now))

    assert polymarket.activity_limits == [12]
