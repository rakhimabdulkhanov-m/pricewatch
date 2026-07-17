"""PriceWatch orchestrator.

Usage:
    python -m monitor.run [--dry-run]

--dry-run  Fetch and diff, but do NOT write state back to disk.
           Prints events to stdout instead of sending to Telegram/Sheets.
"""

import argparse
import sys
from pathlib import Path

import yaml

from monitor.state import diff, load_state, save_state, utc_now_iso
from monitor.stores.base import FetchError
from monitor.stores.stub import StubAdapter

# ---------------------------------------------------------------------------
# Adapter registry — add real adapters here as T3 implements them.
# ---------------------------------------------------------------------------

_ADAPTERS = {
    "stub": StubAdapter(),
}

STATE_PATH = Path("state/latest.json")
CONFIG_PATH = Path("config/products.yaml")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Fetch phase
# ---------------------------------------------------------------------------

def fetch_all(config: dict) -> tuple[dict, dict]:
    """Fetch all (product, store) combinations defined in config.

    Returns
    -------
    results  : {product_id: {store_id: {price, in_stock, name}}}
               Only entries where the fetch SUCCEEDED.
    failures : {product_id: [store_id, ...]}
               Entries where FetchError was raised.
    """
    results: dict = {}
    failures: dict = {}

    enabled_stores: list[str] = config.get("stores", [])

    for product in config.get("products", []):
        product_id = product["id"]
        urls: dict[str, str] = product.get("urls", {})

        for store_id in enabled_stores:
            url = urls.get(store_id)
            if url is None:
                # Product has no URL configured for this store — skip silently.
                continue

            adapter = _ADAPTERS.get(store_id)
            if adapter is None:
                print(f"[WARN] No adapter registered for store '{store_id}' — skipping.")
                continue

            try:
                data = adapter.fetch_product(url)
                results.setdefault(product_id, {})[store_id] = data
                print(f"[OK]   {product_id}/{store_id}: {data['price']} UAH "
                      f"({'in stock' if data['in_stock'] else 'OUT OF STOCK'})")
            except FetchError as exc:
                print(f"[FAIL] {product_id}/{store_id}: {exc}")
                failures.setdefault(product_id, []).append(store_id)

    return results, failures


# ---------------------------------------------------------------------------
# Notify / Sheets hooks (stubs until T5/T6)
# ---------------------------------------------------------------------------

def notify_hook(events: list[dict], dry_run: bool) -> None:
    """T6: send events to Telegram channel.  Currently prints only."""
    if not events:
        return
    print("\n--- Events ---")
    for event in events:
        _print_event(event)


def sheets_hook(results: dict, timestamp: str, dry_run: bool) -> None:
    """T5: append rows to Google Sheets.  Currently a no-op."""
    # Placeholder: sheets.append_rows(spreadsheet_id, rows, credentials)
    pass


def _print_event(event: dict) -> None:
    t = event["type"]
    pid = event["product_id"]
    sid = event["store_id"]
    if t == "price_change":
        old = event["old_price"]
        new = event["new_price"]
        pct = (new - old) / old * 100
        sign = "+" if pct > 0 else ""
        print(f"  PRICE  {pid}/{sid}: {old} -> {new} UAH ({sign}{pct:.1f}%)")
    elif t == "stock_change":
        direction = "back IN stock" if event["new_in_stock"] else "OUT OF stock"
        print(f"  STOCK  {pid}/{sid}: {direction}")
    elif t == "fetch_warning":
        n = event["consecutive_failures"]
        print(f"  WARN   {pid}/{sid}: {n} consecutive fetch failures")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="PriceWatch orchestrator")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and diff without writing state to disk.")
    args = parser.parse_args()

    dry_run: bool = args.dry_run

    if dry_run:
        print("[DRY-RUN] State will NOT be written.\n")

    # 1. Load config and state.
    config = load_config(CONFIG_PATH)
    state = load_state(STATE_PATH)

    # 2. Fetch phase.
    results, failures = fetch_all(config)

    # 3. Diff phase.
    timestamp = utc_now_iso()
    events = diff(state, results, failures)

    # 4. Notify hook (T6).
    notify_hook(events, dry_run=dry_run)

    # 5. Sheets hook (T5).
    sheets_hook(results, timestamp, dry_run=dry_run)

    # 6. Persist state (skipped in dry-run).
    if not dry_run:
        state["checked_at"] = timestamp
        save_state(STATE_PATH, state)
        print(f"\nState saved to {STATE_PATH} at {timestamp}.")
    else:
        print(f"\n[DRY-RUN] Would have saved state at {timestamp}. Skipping.")

    if not events:
        print("No changes detected.")


if __name__ == "__main__":
    main()
