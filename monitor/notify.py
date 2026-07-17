"""Telegram channel notifier.

Filled in during T6.

Planned public interface:

    send_events(events: list[dict], bot_token: str, chat_id: str) -> None

        Posts a formatted message to a Telegram channel for each event
        in *events* (price_change, stock_change, fetch_warning).

        bot_token and chat_id are passed via environment variables
        TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.

        Price-change message format (example):
            Apple iPhone 15 128GB
            Comfy: 32 999 UAH -> 31 499 UAH (-4.5%)

        Stock-back-in message triggers an @channel mention.

Uses httpx (already in requirements.txt); no additional dependencies.
"""
