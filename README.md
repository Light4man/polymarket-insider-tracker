# Polymarket Wallet Tracker

Python worker that watches Polymarket for suspicious new-wallet whale trades, sends Telegram alerts, and posts a daily rolling 24h summary.

## What It Does

- Polls recent Polymarket trades from the public data API.
- Enriches each candidate trade with wallet profile age and executed trade activity.
- Classifies suspicious trades as:
  - `RED`: account age `< RED_MAX_ACCOUNT_AGE_HOURS`, executed trades `< RED_MAX_EXECUTED_TRADES`, bet size `>= RED_THRESHOLD_USD`
  - `YELLOW`: account age `< YELLOW_MAX_ACCOUNT_AGE_DAYS`, executed trades `< YELLOW_MAX_EXECUTED_TRADES`, bet size `>= YELLOW_THRESHOLD_USD`
- Sends formatted Telegram alerts with market, outcome, USD size, wallet join date, transaction link, and profile link.
- Stores seen trade rows and sent alerts in SQLite so restarts do not resend alerts.
- Sends one scheduled summary per day showing the top alert-triggered markets over the last 24 hours.

## Setup

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
pip install -e .[dev]
```

3. Copy `.env.example` to `.env` and fill in the Telegram values.
4. Make sure the Telegram bot is already added to the target chat or channel with permission to post.
5. Use a real Telegram destination in `TELEGRAM_ALERT_CHAT_ID`:
   - channel username like `@my_alerts_channel`, or
   - numeric chat id like `-1001234567890`
   - do not leave the example value `@your_alert_channel`

## Configuration

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_ALERT_CHAT_ID` | Chat or channel for live alerts |
| `TELEGRAM_SUMMARY_CHAT_ID` | Optional chat/channel for summaries; defaults to alert chat |
| `RED_THRESHOLD_USD` | Default `9950` |
| `RED_MAX_ACCOUNT_AGE_HOURS` | Default `24` |
| `RED_MAX_EXECUTED_TRADES` | Default `3` |
| `YELLOW_THRESHOLD_USD` | Default `4949` |
| `YELLOW_MAX_ACCOUNT_AGE_DAYS` | Default `10` |
| `YELLOW_MAX_EXECUTED_TRADES` | Default `10` |
| `POLL_INTERVAL_SECONDS` | Default `5` |
| `SUMMARY_TIME` | Daily summary time, `HH:MM` |
| `SUMMARY_TIMEZONE` | IANA timezone, for example `Europe/Kiev` |
| `SUMMARY_TOP_N` | Number of markets in summary |
| `SQLITE_PATH` | SQLite database path |
| `LOG_LEVEL` | Logging level |

## Run

```bash
python -m app.main
```

The service will create the SQLite database automatically if it does not exist.

## Test

```bash
pytest
```
