"""Google Sheets history writer — PriceWatch.

Public interface
----------------
post_rows(rows)             -> bool
get_history(days=30)        -> list | None
rows_from_results(results, checked_at) -> list

Environment
-----------
SHEETS_WEBHOOK_URL  Google Apps Script /exec URL (set in .env).
"""

import os
import sys

import httpx

_ENV_KEY = "SHEETS_WEBHOOK_URL"

# Connect timeout kept tight; total allows for the Apps Script redirect to
# script.googleusercontent.com plus actual script execution.
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def post_rows(rows: list) -> bool:
    """POST *rows* to the Sheets webhook.

    Parameters
    ----------
    rows:
        List of lists in column order:
        [checked_at_utc, store, product_id, name, price_uah, in_stock]

    Returns
    -------
    True on success, False on any failure.
    Never raises — Sheets being down must not kill the monitoring run.
    """
    url = os.environ.get(_ENV_KEY, "")
    if not url:
        print(f"[sheets] {_ENV_KEY} not set — skipping Sheets post", file=sys.stderr)
        return False
    try:
        resp = httpx.post(
            url,
            json={"rows": rows},
            follow_redirects=True,
            timeout=_TIMEOUT,
        )
        body = resp.json()
        if not body.get("ok"):
            print(f"[sheets] API returned error: {body}", file=sys.stderr)
            return False
        return True
    except Exception as exc:  # network, JSON parse, etc.
        print(f"[sheets] post_rows failed: {exc}", file=sys.stderr)
        return False


def get_history(days: int = 30) -> list | None:
    """GET history rows from the Sheets webhook for the last *days* days.

    Returns
    -------
    List of dicts on success, None on any failure.
    """
    url = os.environ.get(_ENV_KEY, "")
    if not url:
        print(f"[sheets] {_ENV_KEY} not set — skipping get_history", file=sys.stderr)
        return None
    try:
        resp = httpx.get(
            url,
            params={"days": days},
            follow_redirects=True,
            timeout=_TIMEOUT,
        )
        return resp.json()
    except Exception as exc:
        print(f"[sheets] get_history failed: {exc}", file=sys.stderr)
        return None


def rows_from_results(results: dict, checked_at: str) -> list:
    """Build sheet rows from a run's fetch results.

    Parameters
    ----------
    results:
        {product_id: {store_id: {price, in_stock, name}}}
        Only successfully fetched entries (same shape as run.py's results dict).
    checked_at:
        ISO-8601 UTC timestamp string for this run (e.g. "2026-07-17T10:00:00Z").

    Returns
    -------
    List of rows, each a 6-element list:
        [checked_at_utc, store, product_id, name, price_uah, in_stock]

    Note (T7): on first run old_state has no items so diff() produces no
    price_change/stock_change events and the caller passes an empty filtered
    results dict — nothing is posted.  A seed-snapshot feature (post ALL
    results on first run regardless of events) is deferred to T7.
    """
    rows = []
    for product_id, store_map in results.items():
        for store_id, data in store_map.items():
            rows.append([
                checked_at,
                store_id,
                product_id,
                data["name"],
                data["price"],
                data["in_stock"],
            ])
    return rows
