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

from monitor.envfile import load_dotenv
from monitor.state import diff, load_state, save_state, utc_now_iso
from monitor.stores import get_adapter
from monitor.stores.base import FetchError

# Load .env for local development (keys already in the environment take priority).
load_dotenv(".env")

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

            adapter = get_adapter(store_id)
            if adapter is None:
                print(f"[WARN] No adapter registered for store '{store_id}' — skipping.")
                continue

            try:
                data = adapter.fetch_product(url)
                results.setdefault(product_id, {})[store_id] = data
                print(f"[OK]   {product_id}/{store_id}: {data['price']} UAH "
                      f"({'in stock' if data['in_stock'] else 'OUT OF STOCK'})")
            except FetchError as exc:
                print(f"[FAIL] {product_id}/{store_id}: {exc}", file=sys.stderr)
                failures.setdefault(product_id, []).append(store_id)

    return results, failures


# ---------------------------------------------------------------------------
# Pair counting
# ---------------------------------------------------------------------------

def _count_pairs(d: dict) -> int:
    """Count (product, store) pairs in a results or failures dict.

    Works for both shapes:
        results:  {product_id: {store_id: data}}
        failures: {product_id: [store_id, ...]}
    """
    total = 0
    for v in d.values():
        total += len(v)
    return total


# ---------------------------------------------------------------------------
# Notify hooks
# ---------------------------------------------------------------------------

def seed_notify_hook(results: dict, dry_run: bool) -> None:
    """Send the single 'PriceWatch is live' message on first run.

    On first run (no prior state items) exactly one channel message is sent
    instead of per-product notifications so the channel is not flooded.
    """
    n_products = len(results)
    n_stores = len({sid for sm in results.values() for sid in sm})
    product_word = "product" if n_products == 1 else "products"
    store_word = "store" if n_stores == 1 else "stores"
    text = (
        f"PriceWatch is live. "
        f"Tracking {n_products} {product_word} across {n_stores} {store_word}."
    )
    if dry_run:
        print(f"[DRY-RUN] Seed message: {text}")
        return
    from monitor import notify
    notify.send_message(text)


def notify_hook(events: list[dict], dry_run: bool,
                products_by_id: dict | None = None) -> None:
    """Send change events to the Telegram channel.

    In dry-run mode events are printed to stdout only.
    """
    if not events:
        return
    print("\n--- Events ---")
    for event in events:
        _print_event(event)
    if dry_run:
        return
    from monitor import notify
    notify.notify_events(events, products_by_id or {})


# ---------------------------------------------------------------------------
# Sheets hooks
# ---------------------------------------------------------------------------

def seed_sheets_hook(results: dict, timestamp: str, dry_run: bool) -> int:
    """Post a full snapshot to Sheets on first run.

    Returns the number of rows posted (0 in dry-run or on failure).
    """
    from monitor import sheets
    rows = sheets.rows_from_results(results, timestamp)
    if not rows:
        return 0
    if dry_run:
        print(f"[DRY-RUN] Would post {len(rows)} seed row(s) to Sheets.")
        return 0
    ok = sheets.post_rows(rows)
    if ok:
        print(f"[Sheets] Posted {len(rows)} seed row(s).")
        return len(rows)
    return 0


def sheets_hook(results: dict, events: list[dict], timestamp: str, dry_run: bool) -> int:
    """Post changed rows to Google Sheets.

    Only rows where a price_change or stock_change event occurred are posted.
    Returns the number of rows posted (0 in dry-run or if nothing changed).
    """
    changed_pairs: set[tuple[str, str]] = set()
    for ev in events:
        if ev["type"] in ("price_change", "stock_change"):
            changed_pairs.add((ev["product_id"], ev["store_id"]))

    if not changed_pairs:
        return 0

    # Build a filtered results dict containing only changed pairs.
    changed_results: dict = {}
    for product_id, store_map in results.items():
        for store_id, data in store_map.items():
            if (product_id, store_id) in changed_pairs:
                changed_results.setdefault(product_id, {})[store_id] = data

    from monitor import sheets
    rows = sheets.rows_from_results(changed_results, timestamp)
    if not rows:
        return 0

    if dry_run:
        print(f"[DRY-RUN] Would post {len(rows)} row(s) to Sheets.")
        return 0

    ok = sheets.post_rows(rows)
    if ok:
        print(f"[Sheets] Posted {len(rows)} row(s).")
        return len(rows)
    return 0


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
    parser.add_argument("--config", type=Path, default=CONFIG_PATH,
                        help="Path to the products YAML (default: config/products.yaml). "
                             "Use a store-specific config to run one store separately, "
                             "e.g. the residential Rozetka leg.")
    parser.add_argument("--state", type=Path, default=STATE_PATH,
                        help="Path to the state JSON (default: state/latest.json). "
                             "Pair a separate config with its OWN state file so an "
                             "out-of-band run never collides with the cron's state.")
    args = parser.parse_args()

    dry_run: bool = args.dry_run
    config_path: Path = args.config
    state_path: Path = args.state

    if dry_run:
        print("[DRY-RUN] State will NOT be written.\n")

    # 1. Load config and state.
    config = load_config(config_path)
    state = load_state(state_path)

    # Detect seed run: no prior items in state (first run or wiped state).
    is_seed = not state.get("items")

    # 2. Fetch phase (sequential; adapters already jitter 2-4 s each so a
    #    run over 30-40 URLs takes several minutes — that is expected and fine).
    results, failures = fetch_all(config)

    # 3. Diff phase — mutates state in place with fresh data.
    timestamp = utc_now_iso()
    events = diff(state, results, failures)

    # 4. Count attempts for summary and exit-code decision.
    n_ok = _count_pairs(results)
    n_fail = _count_pairs(failures)
    n_total = n_ok + n_fail

    # 5. Notify BEFORE Sheets and state save.
    #    Ordering guarantee: a crash after notify but before save_state causes a
    #    duplicate notification on retry — that is acceptable.  The inverse
    #    (saving state before notifying) would silently swallow changes.
    if is_seed:
        # First run: one channel message, full snapshot to Sheets, no per-product flood.
        seed_notify_hook(results, dry_run=dry_run)
        n_rows = seed_sheets_hook(results, timestamp, dry_run=dry_run)
        n_events = 0
    else:
        # Normal run: per-event notifications, only changed rows to Sheets.
        products_by_id = {p["id"]: p for p in config.get("products", [])}
        notify_hook(events, dry_run=dry_run, products_by_id=products_by_id)
        n_rows = sheets_hook(results, events, timestamp, dry_run=dry_run)
        n_events = sum(
            1 for e in events if e["type"] in ("price_change", "stock_change")
        )

    # 6. Save state LAST so a crash mid-run cannot mark changes as seen
    #    without having reported them first.
    if not dry_run:
        state["checked_at"] = timestamp
        save_state(state_path, state)

    # 7. Run summary (appears in GitHub Actions log; keep it readable).
    print(
        f"\nRun complete: {n_ok} fetched, {n_fail} failure(s), "
        f"{n_events} event(s), {n_rows} sheet row(s) posted."
    )

    # 8. Exit 1 only when strictly more than half of all attempts failed.
    #    This makes a genuinely broken run show red in Actions while normal
    #    flakiness (a few 403s from bot-detection) stays green.
    if n_total > 0 and n_fail / n_total > 0.5:
        sys.exit(1)


if __name__ == "__main__":
    main()
