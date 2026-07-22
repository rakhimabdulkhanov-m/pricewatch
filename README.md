# PriceWatch

Price and stock monitor for Ukrainian electronics stores.

Runs on a GitHub Actions cron schedule, writes history to Google Sheets,
and posts price-change and restock alerts to a Telegram channel.

## What it does

- Checks configured product URLs across multiple stores on each run.
- Includes a Rozetka adapter that passes Cloudflare's TLS fingerprinting for
  public product data (see [BYPASS.md](BYPASS.md); `python scripts/rozetka_demo.py`).
- Detects price changes and stock transitions (in-stock / out-of-stock).
- Appends a timestamped row to a Google Sheets tab for every checked item.
- Sends a Telegram message for every significant event.
- Produces a weekly price-history chart posted to the same channel.

## Quick start (local, dry-run)

```
pip install -r requirements.txt
python -m monitor.run --dry-run
```

`--dry-run` fetches via the stub adapter and prints events without writing
state or calling external services.

## Configuration

Edit `config/products.yaml` to add stores and products.
Set environment variables before a live run:

| Variable              | Purpose                              |
|-----------------------|--------------------------------------|
| `TELEGRAM_BOT_TOKEN`  | Bot token for notifications          |
| `TELEGRAM_CHAT_ID`    | Target channel / chat ID             |
| `GOOGLE_CREDENTIALS`  | Path to service-account JSON key     |
| `SPREADSHEET_ID`      | Google Sheets spreadsheet ID         |

## Project layout

```
monitor/          Python package
  run.py          Orchestrator entry point
  state.py        State persistence and change detection
  stores/         Store adapter plugins
  jsonld.py       JSON-LD price extractor (T3)
  sheets.py       Google Sheets writer (T5)
  notify.py       Telegram notifier (T6)
  report.py       Weekly summary builder (T8)
  chartstyle.py   Matplotlib style helpers (T8)
config/           YAML configuration
state/            Persisted run state (JSON)
```
