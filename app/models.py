from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal


def _parse_decimal(value: object) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True)
class TradeRecord:
    proxy_wallet: str
    side: str
    asset: str
    condition_id: str
    size: Decimal
    price: Decimal
    timestamp: datetime
    title: str
    slug: str
    outcome: str
    transaction_hash: str
    event_slug: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, object]) -> "TradeRecord":
        return cls(
            proxy_wallet=str(payload["proxyWallet"]),
            side=str(payload["side"]),
            asset=str(payload["asset"]),
            condition_id=str(payload["conditionId"]),
            size=_parse_decimal(payload["size"]),
            price=_parse_decimal(payload["price"]),
            timestamp=datetime.fromtimestamp(int(payload["timestamp"]), tz=UTC),
            title=str(payload["title"]),
            slug=str(payload["slug"]),
            outcome=str(payload["outcome"]),
            transaction_hash=str(payload["transactionHash"]),
            event_slug=(
                str(payload["eventSlug"])
                if payload.get("eventSlug") is not None
                else None
            ),
        )

    @property
    def dedupe_key(self) -> str:
        return "|".join(
            [
                self.transaction_hash.lower(),
                self.proxy_wallet.lower(),
                self.asset,
                self.side,
                format(self.size.normalize(), "f"),
                format(self.price.normalize(), "f"),
            ]
        )


@dataclass(frozen=True)
class UserActivity:
    proxy_wallet: str
    timestamp: datetime
    condition_id: str
    trade_type: str
    size: Decimal
    usdc_size: Decimal
    transaction_hash: str
    price: Decimal
    asset: str
    side: str
    outcome: str
    title: str
    slug: str

    @classmethod
    def from_api(cls, payload: dict[str, object]) -> "UserActivity":
        return cls(
            proxy_wallet=str(payload["proxyWallet"]),
            timestamp=datetime.fromtimestamp(int(payload["timestamp"]), tz=UTC),
            condition_id=str(payload["conditionId"]),
            trade_type=str(payload["type"]),
            size=_parse_decimal(payload["size"]),
            usdc_size=_parse_decimal(payload["usdcSize"]),
            transaction_hash=str(payload["transactionHash"]),
            price=_parse_decimal(payload["price"]),
            asset=str(payload["asset"]),
            side=str(payload["side"]),
            outcome=str(payload["outcome"]),
            title=str(payload["title"]),
            slug=str(payload["slug"]),
        )


@dataclass(frozen=True)
class PublicProfile:
    proxy_wallet: str | None
    created_at: datetime | None

    @classmethod
    def from_api(cls, payload: dict[str, object]) -> "PublicProfile":
        raw_created_at = payload.get("createdAt")
        created_at = (
            datetime.fromisoformat(str(raw_created_at).replace("Z", "+00:00"))
            if raw_created_at
            else None
        )
        proxy_wallet = payload.get("proxyWallet")
        return cls(
            proxy_wallet=str(proxy_wallet) if proxy_wallet else None,
            created_at=created_at,
        )


@dataclass(frozen=True)
class AlertCandidate:
    severity: str
    trade: TradeRecord
    matched_activity: UserActivity
    joined_at: datetime
    executed_trade_count: int
    bet_size_usd: Decimal


@dataclass(frozen=True)
class SummaryRow:
    market_title: str
    total_usd: Decimal
