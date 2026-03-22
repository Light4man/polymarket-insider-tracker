from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.models import AlertCandidate, SummaryRow


class Storage:
    def __init__(self, path: str | Path) -> None:
        raw_path = Path(path)
        if str(raw_path) != ":memory:":
            raw_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(raw_path)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS seen_trade_rows (
                dedupe_key TEXT PRIMARY KEY,
                transaction_hash TEXT NOT NULL,
                wallet TEXT NOT NULL,
                seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sent_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dedupe_key TEXT NOT NULL UNIQUE,
                severity TEXT NOT NULL,
                wallet TEXT NOT NULL,
                transaction_hash TEXT NOT NULL,
                market_title TEXT NOT NULL,
                market_slug TEXT NOT NULL,
                usd_size TEXT NOT NULL,
                alerted_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wallet_profiles (
                wallet TEXT PRIMARY KEY,
                created_at TEXT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS summary_runs (
                summary_date TEXT PRIMARY KEY,
                sent_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def has_seen_trade(self, dedupe_key: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM seen_trade_rows WHERE dedupe_key = ?",
            (dedupe_key,),
        ).fetchone()
        return row is not None

    def mark_trade_seen(
        self,
        dedupe_key: str,
        *,
        transaction_hash: str,
        wallet: str,
        seen_at: datetime,
    ) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO seen_trade_rows
            (dedupe_key, transaction_hash, wallet, seen_at)
            VALUES (?, ?, ?, ?)
            """,
            (dedupe_key, transaction_hash, wallet, seen_at.astimezone(UTC).isoformat()),
        )
        self.connection.commit()

    def record_alert(self, candidate: AlertCandidate, alerted_at: datetime) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO sent_alerts
            (dedupe_key, severity, wallet, transaction_hash, market_title, market_slug, usd_size, alerted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.trade.dedupe_key,
                candidate.severity,
                candidate.trade.proxy_wallet,
                candidate.trade.transaction_hash,
                candidate.trade.title,
                candidate.trade.slug,
                str(candidate.bet_size_usd),
                alerted_at.astimezone(UTC).isoformat(),
            ),
        )
        self.connection.commit()

    def get_cached_profile(self, wallet: str) -> tuple[bool, datetime | None]:
        row = self.connection.execute(
            "SELECT created_at FROM wallet_profiles WHERE wallet = ?",
            (wallet,),
        ).fetchone()
        if row is None:
            return False, None
        raw_created_at = row["created_at"]
        created_at = (
            datetime.fromisoformat(raw_created_at) if raw_created_at else None
        )
        return True, created_at

    def upsert_wallet_profile(
        self,
        wallet: str,
        *,
        created_at: datetime | None,
        fetched_at: datetime,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO wallet_profiles (wallet, created_at, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(wallet) DO UPDATE SET
                created_at = excluded.created_at,
                fetched_at = excluded.fetched_at
            """,
            (
                wallet,
                created_at.isoformat() if created_at else None,
                fetched_at.astimezone(UTC).isoformat(),
            ),
        )
        self.connection.commit()

    def summary_already_sent(self, summary_date: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM summary_runs WHERE summary_date = ?",
            (summary_date,),
        ).fetchone()
        return row is not None

    def mark_summary_sent(self, summary_date: str, sent_at: datetime) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO summary_runs (summary_date, sent_at)
            VALUES (?, ?)
            """,
            (summary_date, sent_at.astimezone(UTC).isoformat()),
        )
        self.connection.commit()

    def get_summary_market_totals(
        self,
        *,
        since: datetime,
        limit: int,
    ) -> list[SummaryRow]:
        rows = self.connection.execute(
            """
            SELECT market_title, SUM(CAST(usd_size AS REAL)) AS total_usd
            FROM sent_alerts
            WHERE alerted_at >= ?
            GROUP BY market_title
            ORDER BY total_usd DESC, market_title ASC
            LIMIT ?
            """,
            (since.astimezone(UTC).isoformat(), limit),
        ).fetchall()
        return [
            SummaryRow(
                market_title=str(row["market_title"]),
                total_usd=Decimal(str(row["total_usd"])),
            )
            for row in rows
        ]
