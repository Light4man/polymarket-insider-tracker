from __future__ import annotations

from decimal import Decimal

import httpx

from app.models import PublicProfile, TradeRecord, UserActivity


class PolymarketClient:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_recent_trades(
        self,
        min_usd: Decimal | str,
        *,
        limit: int = 100,
        taker_only: bool = False,
    ) -> list[TradeRecord]:
        response = await self._client.get(
            "https://data-api.polymarket.com/trades",
            params={
                "limit": limit,
                "filterType": "CASH",
                "filterAmount": str(min_usd),
                "takerOnly": str(taker_only).lower(),
            },
        )
        response.raise_for_status()
        payload = response.json()
        return [TradeRecord.from_api(item) for item in payload]

    async def fetch_user_activity(
        self,
        wallet: str,
        *,
        limit: int = 10,
    ) -> list[UserActivity]:
        response = await self._client.get(
            "https://data-api.polymarket.com/activity",
            params={"user": wallet, "type": "TRADE", "limit": limit},
        )
        response.raise_for_status()
        payload = response.json()
        return [UserActivity.from_api(item) for item in payload]

    async def fetch_public_profile(self, wallet: str) -> PublicProfile | None:
        response = await self._client.get(
            "https://gamma-api.polymarket.com/public-profile",
            params={"address": wallet},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return PublicProfile.from_api(response.json())
