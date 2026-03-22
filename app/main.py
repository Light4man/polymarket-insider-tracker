from __future__ import annotations

import asyncio
import logging

from app.polymarket import PolymarketClient
from app.service import TrackerService
from app.settings import Settings
from app.storage import Storage
from app.telegram import TelegramClient


async def _main() -> None:
    settings = Settings.from_env()
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    storage = Storage(settings.sqlite_path)
    polymarket_client = PolymarketClient(settings.request_timeout_seconds)
    telegram_client = TelegramClient(
        settings.telegram_bot_token,
        settings.request_timeout_seconds,
    )
    service = TrackerService(
        settings=settings,
        polymarket_client=polymarket_client,
        telegram_client=telegram_client,
        storage=storage,
    )

    try:
        await service.run()
    finally:
        storage.close()
        await polymarket_client.aclose()
        await telegram_client.aclose()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
