"""State persistence and change-detection for PriceWatch.

State file shape (state/latest.json):
{
  "checked_at": "2026-07-18T09:17:03Z",   # ISO-8601 UTC, null on first run
  "items": {
    "<product-id>": {
      "<store-id>": {"price": 32999, "in_stock": true, "name": "..."}
    }
  },
  "_failures": {
    "<product-id>/<store-id>": <int consecutive-failure-count>
  }
}

Rules:
- Prices are integer UAH; timestamps ISO-8601 UTC.
- A failed fetch leaves the (product, store) key ABSENT for that run.
  It is NOT treated as out-of-stock.
- Consecutive failure counter increments each run the fetch fails; resets
  to 0 on success.  A warning event is emitted only after 2 consecutive
  failures (i.e. counter reaches 2 on the second failed run).
- A single 403 (one failure) produces no event at all.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_state(path: str | Path) -> dict:
    """Load and return the state dict from *path*.

    If the file does not exist or is empty, returns a blank state.
    """
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return {"checked_at": None, "items": {}, "_failures": {}}
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    # Back-fill missing keys so callers never have to guard.
    data.setdefault("items", {})
    data.setdefault("_failures", {})
    return data


def save_state(path: str | Path, state: dict) -> None:
    """Write *state* to *path* as formatted JSON (UTF-8, 2-space indent)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

def diff(old_state: dict, new_results: dict, failures: dict[str, list[str]]) -> list[dict]:
    """Compute change events between a previous state and fresh fetch results.

    Parameters
    ----------
    old_state:
        The dict returned by load_state() before this run.
    new_results:
        Successful fetches structured as
        {product_id: {store_id: {price, in_stock, name}}}.
        Only products/stores where the fetch SUCCEEDED appear here.
    failures:
        Stores that failed this run, structured as
        {product_id: [store_id, ...]}.

    Returns
    -------
    A list of event dicts.  Each event has at minimum:
        type        str   "price_change" | "stock_change" | "fetch_warning"
        product_id  str
        store_id    str

    price_change also has: old_price, new_price
    stock_change also has: old_in_stock, new_in_stock
    fetch_warning also has: consecutive_failures (int)

    The function MUTATES old_state in place:
    - Updates items with new results.
    - Updates _failures counters.
    - Does NOT update checked_at (the caller sets that before save_state).
    """
    events: list[dict] = []
    old_items = old_state.setdefault("items", {})
    failure_counts = old_state.setdefault("_failures", {})

    # --- process successful fetches ---
    for product_id, store_map in new_results.items():
        for store_id, fresh in store_map.items():
            key = f"{product_id}/{store_id}"

            # Reset failure counter on success.
            failure_counts.pop(key, None)

            old_entry = old_items.get(product_id, {}).get(store_id)

            if old_entry is not None:
                # Price change
                if fresh["price"] != old_entry["price"]:
                    events.append({
                        "type": "price_change",
                        "product_id": product_id,
                        "store_id": store_id,
                        "old_price": old_entry["price"],
                        "new_price": fresh["price"],
                        "name": fresh["name"],
                    })
                # Stock transition
                if fresh["in_stock"] != old_entry["in_stock"]:
                    events.append({
                        "type": "stock_change",
                        "product_id": product_id,
                        "store_id": store_id,
                        "old_in_stock": old_entry["in_stock"],
                        "new_in_stock": fresh["in_stock"],
                        "name": fresh["name"],
                    })

            # Update state with fresh data.
            old_items.setdefault(product_id, {})[store_id] = fresh

    # --- process failures ---
    for product_id, failed_stores in failures.items():
        for store_id in failed_stores:
            key = f"{product_id}/{store_id}"
            count = failure_counts.get(key, 0) + 1
            failure_counts[key] = count
            if count >= 2:
                events.append({
                    "type": "fetch_warning",
                    "product_id": product_id,
                    "store_id": store_id,
                    "consecutive_failures": count,
                })

    return events


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string ending in 'Z'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
