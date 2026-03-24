from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _require(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _validate_telegram_value(name: str, value: str) -> str:
    placeholders = {
        "your_bot_token",
        "@your_alert_channel",
        "@your_summary_channel",
    }
    if value in placeholders or value.startswith("your_"):
        raise ValueError(
            f"Environment variable {name} still has a placeholder value: {value}"
        )
    return value


def _parse_time(value: str) -> time:
    hours, minutes = value.split(":", 1)
    return time(hour=int(hours), minute=int(minutes))


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_alert_chat_id: str
    telegram_summary_chat_id: str
    outcome_price_max: Decimal
    red_threshold_usd: Decimal
    red_max_account_age_hours: int
    red_max_executed_trades: int
    yellow_threshold_usd: Decimal
    yellow_max_account_age_days: int
    yellow_max_executed_trades: int
    poll_interval_seconds: int
    summary_time: time
    summary_timezone: str
    summary_top_n: int
    sqlite_path: Path
    log_level: str
    request_timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        alert_chat_id = _validate_telegram_value(
            "TELEGRAM_ALERT_CHAT_ID",
            _require("TELEGRAM_ALERT_CHAT_ID"),
        )
        summary_chat_id = os.getenv("TELEGRAM_SUMMARY_CHAT_ID") or alert_chat_id
        if summary_chat_id:
            summary_chat_id = _validate_telegram_value(
                "TELEGRAM_SUMMARY_CHAT_ID",
                summary_chat_id,
            )
        return cls(
            telegram_bot_token=_validate_telegram_value(
                "TELEGRAM_BOT_TOKEN",
                _require("TELEGRAM_BOT_TOKEN"),
            ),
            telegram_alert_chat_id=alert_chat_id,
            telegram_summary_chat_id=summary_chat_id,
            outcome_price_max=Decimal(os.getenv("OUTCOME_PRICE_MAX", "0.95")),
            red_threshold_usd=Decimal(os.getenv("RED_THRESHOLD_USD", "9950")),
            red_max_account_age_hours=int(
                os.getenv("RED_MAX_ACCOUNT_AGE_HOURS", "24")
            ),
            red_max_executed_trades=int(os.getenv("RED_MAX_EXECUTED_TRADES", "3")),
            yellow_threshold_usd=Decimal(os.getenv("YELLOW_THRESHOLD_USD", "4949")),
            yellow_max_account_age_days=int(
                os.getenv("YELLOW_MAX_ACCOUNT_AGE_DAYS", "10")
            ),
            yellow_max_executed_trades=int(
                os.getenv("YELLOW_MAX_EXECUTED_TRADES", "10")
            ),
            poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "5")),
            summary_time=_parse_time(os.getenv("SUMMARY_TIME", "23:55")),
            summary_timezone=os.getenv("SUMMARY_TIMEZONE", "UTC"),
            summary_top_n=int(os.getenv("SUMMARY_TOP_N", "10")),
            sqlite_path=Path(os.getenv("SQLITE_PATH", "./data/tracker.db")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
