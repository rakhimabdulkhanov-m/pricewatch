"""Telegram channel notifier for PriceWatch.

Public interface
----------------
format_event(event)              -> str   HTML message text for one event
send_message(text)               -> bool  POST sendMessage; retries on failure
send_photo(image_path, caption)  -> bool  POST sendPhoto;   retries on failure
notify_events(events, products_by_id)     route events; digest when >10

Environment variables (never hardcoded here):
    TG_BOT_TOKEN   — bot token from @BotFather
    TG_CHANNEL_ID  — channel username (@handle) or numeric id
"""

import html
import os
import sys
import time
from pathlib import Path

import httpx

# Unicode constants used in formatting.
_THIN = " "    # THIN SPACE — thousands separator
_MINUS = "−"   # MINUS SIGN — for negative percents
_ARROW = "→"   # RIGHTWARDS ARROW — between old and new price
_UAH = "₴"     # HRYVNIA SIGN
_UP = "\U0001f53a"  # 🔺
_DOWN = "\U0001f53b"  # 🔻
_BOX = "\U0001f4e6"  # 📦


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_price(amount: int) -> str:
    """Format integer UAH with thin-space thousands separator.

    Example: 32999 -> '32 99'
    """
    s = str(amount)
    groups: list[str] = []
    while len(s) > 3:
        groups.append(s[-3:])
        s = s[:-3]
    groups.append(s)
    return _THIN.join(reversed(groups))


def _fmt_pct(old: int, new: int) -> str:
    """Return formatted percent change string.

    Negative results use true minus (U+2212); positive use '+'.
    One decimal place.  Example: -4.5% -> '−4.5%'
    """
    pct = (new - old) / old * 100
    if pct < 0:
        return f"{_MINUS}{abs(pct):.1f}%"
    return f"+{pct:.1f}%"


# ---------------------------------------------------------------------------
# Public: format_event
# ---------------------------------------------------------------------------

def format_event(event: dict) -> str:
    """Return HTML-mode Telegram message text for a single price or stock event.

    The event dict must include a 'url' key (added by notify_events before
    calling this function).  All store-sourced strings are HTML-escaped.
    """
    t = event["type"]
    name = html.escape(event["name"])
    store = event["store_id"].capitalize()
    url = html.escape(event.get("url", ""))

    if t == "price_change":
        old_p = event["old_price"]
        new_p = event["new_price"]
        arrow = _UP if new_p > old_p else _DOWN
        pct = _fmt_pct(old_p, new_p)
        return (
            f"{arrow} <b>{name}</b>\n"
            f"{store}: {_fmt_price(old_p)} {_ARROW} {_fmt_price(new_p)} {_UAH} ({pct})\n"
            f'<a href="{url}">product page</a>'
        )

    if t == "stock_change":
        stock_line = "back in stock" if event["new_in_stock"] else "out of stock"
        return (
            f"{_BOX} <b>{name}</b>\n"
            f"{store}: {stock_line}\n"
            f'<a href="{url}">product page</a>'
        )

    raise ValueError(f"format_event: unsupported event type '{t}'")


# ---------------------------------------------------------------------------
# Telegram API helpers
# ---------------------------------------------------------------------------

def _base_url() -> str:
    token = os.environ.get("TG_BOT_TOKEN", "")
    return f"https://api.telegram.org/bot{token}"


def _post_with_retry(url: str, *, json_payload: dict | None = None,
                     data: dict | None = None,
                     files: dict | None = None,
                     timeout: float = 15.0) -> dict | None:
    """POST to *url*; retry up to 2 times (2 s, 4 s backoff).

    Returns the parsed JSON dict on success, or None after all retries failed.
    Errors are logged to stderr; exceptions are never raised.
    """
    delays = [2, 4]
    for attempt in range(3):
        try:
            if json_payload is not None:
                resp = httpx.post(url, json=json_payload, timeout=timeout)
            else:
                resp = httpx.post(url, data=data, files=files, timeout=timeout)
            data_out = resp.json()
            if data_out.get("ok"):
                return data_out
            print(f"[notify] API non-ok response: {data_out}", file=sys.stderr)
        except Exception as exc:
            print(f"[notify] request error (attempt {attempt + 1}/3): {exc}",
                  file=sys.stderr)
        if attempt < 2:
            time.sleep(delays[attempt])
    return None


def send_message(text: str) -> bool:
    """POST sendMessage to the configured channel.

    Returns True on success, False after retries exhausted (never raises).
    """
    chat_id = os.environ.get("TG_CHANNEL_ID", "")
    result = _post_with_retry(
        f"{_base_url()}/sendMessage",
        json_payload={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )
    if result is None:
        print("[notify] send_message failed after retries", file=sys.stderr)
        return False
    return True


def send_photo(image_path: str | Path, caption: str) -> bool:
    """POST sendPhoto (multipart) to the configured channel.

    Returns True on success, False after retries exhausted (never raises).
    """
    chat_id = os.environ.get("TG_CHANNEL_ID", "")
    try:
        photo_bytes = Path(image_path).read_bytes()
    except OSError as exc:
        print(f"[notify] send_photo: cannot read '{image_path}': {exc}",
              file=sys.stderr)
        return False

    result = _post_with_retry(
        f"{_base_url()}/sendPhoto",
        data={
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML",
        },
        files={"photo": ("image.jpg", photo_bytes, "image/jpeg")},
        timeout=30.0,
    )
    if result is None:
        print("[notify] send_photo failed after retries", file=sys.stderr)
        return False
    return True


# ---------------------------------------------------------------------------
# Digest helper
# ---------------------------------------------------------------------------

def _compact_line(ev: dict) -> str:
    """Return a single HTML line for use inside a digest message."""
    name = html.escape(ev["name"])
    store = ev["store_id"].capitalize()
    t = ev["type"]
    if t == "price_change":
        old_p = ev["old_price"]
        new_p = ev["new_price"]
        arrow = _UP if new_p > old_p else _DOWN
        pct = _fmt_pct(old_p, new_p)
        return (
            f"{arrow} <b>{name}</b> {store}: "
            f"{_fmt_price(old_p)} {_ARROW} {_fmt_price(new_p)} {_UAH} ({pct})"
        )
    if t == "stock_change":
        status = "back in stock" if ev["new_in_stock"] else "out of stock"
        return f"{_BOX} <b>{name}</b> {store}: {status}"
    return html.escape(repr(ev))


# ---------------------------------------------------------------------------
# Public: notify_events
# ---------------------------------------------------------------------------

def notify_events(events: list[dict], products_by_id: dict) -> None:
    """Send Telegram notifications for a batch of diff events.

    fetch_warning events are logged to stderr and NOT posted to the channel.

    If the number of postable events exceeds 10, a single digest message is
    sent instead of one message per event.

    products_by_id must have the shape:
        {product_id: {"urls": {store_id: url}, "name": str, ...}}
    """
    postable: list[dict] = []

    for ev in events:
        if ev["type"] == "fetch_warning":
            n = ev["consecutive_failures"]
            print(
                f"[notify] WARN {ev['product_id']}/{ev['store_id']}: "
                f"{n} consecutive fetch failure(s)",
                file=sys.stderr,
            )
            continue
        # Enrich with URL (not stored in the event by diff()).
        enriched = dict(ev)
        pid = ev["product_id"]
        sid = ev["store_id"]
        product = products_by_id.get(pid, {})
        enriched["url"] = product.get("urls", {}).get(sid, "")
        # Backfill name from config if the event somehow lacks it.
        if "name" not in enriched:
            enriched["name"] = product.get("name", pid)
        postable.append(enriched)

    if not postable:
        return

    if len(postable) > 10:
        # Digest path: one message summarising all events.
        n = len(postable)
        lines = [f"<b>{n} price/stock changes this run</b>"]
        for ev in postable[:30]:
            lines.append(_compact_line(ev))
        send_message("\n".join(lines))
    else:
        # Individual path: one message per event, 1 s gap between sends.
        for i, ev in enumerate(postable):
            if i > 0:
                time.sleep(1)
            send_message(format_event(ev))
