"""Unit tests for monitor.run orchestrator.

Covers:
- Seed path: one 'PriceWatch is live' message, full snapshot to Sheets,
  no per-product notifications, state saved.
- Normal path: notify_events called with change events; only changed rows
  posted to Sheets; state saved.
- Exit code: strictly >50% fetch failures -> sys.exit(1); <=50% -> exit 0.
- Dry-run: no state written, no messages or sheet rows sent.
"""

import sys
import unittest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_CONFIG = {
    "stores": ["teststore"],
    "products": [
        {"id": "prod-a", "name": "Product A",
         "urls": {"teststore": "https://example.com/a"}},
        {"id": "prod-b", "name": "Product B",
         "urls": {"teststore": "https://example.com/b"}},
        {"id": "prod-c", "name": "Product C",
         "urls": {"teststore": "https://example.com/c"}},
    ],
}


def _make_results(n: int = 3) -> dict:
    """Return a results dict for the first *n* sample products, all at price 10000."""
    products = _SAMPLE_CONFIG["products"][:n]
    return {
        p["id"]: {
            "teststore": {"price": 10000, "in_stock": True, "name": p["name"]}
        }
        for p in products
    }


def _blank_state() -> dict:
    """Empty state — triggers seed path."""
    return {"checked_at": None, "items": {}, "_failures": {}}


def _seeded_state(results: dict | None = None) -> dict:
    """State matching *results* exactly (same prices — no events on normal run)."""
    if results is None:
        results = _make_results()
    items: dict = {}
    for pid, store_map in results.items():
        items[pid] = {sid: dict(data) for sid, data in store_map.items()}
    return {"checked_at": "2026-07-17T10:00:00Z", "items": items, "_failures": {}}


# ---------------------------------------------------------------------------
# Base: patches shared across all tests
# ---------------------------------------------------------------------------

class _RunTestBase(unittest.TestCase):
    """Mocks out all I/O and external calls; diff() runs for real."""

    def setUp(self):
        # Prevent sys.exit from killing the test runner.
        self._p_exit = patch("sys.exit")
        self.mock_exit = self._p_exit.start()

        # Default argv: no --dry-run.
        self._p_argv = patch.object(sys, "argv", ["monitor.run"])
        self._p_argv.start()

        # Config and state I/O.
        self._p_cfg = patch("monitor.run.load_config",
                            return_value=_SAMPLE_CONFIG)
        self._p_cfg.start()

        self._p_state = patch("monitor.run.load_state",
                              return_value=_blank_state())
        self.mock_load_state = self._p_state.start()

        # Fetch returns 3 successes, no failures by default.
        self._p_fetch = patch("monitor.run.fetch_all",
                              return_value=(_make_results(), {}))
        self.mock_fetch = self._p_fetch.start()

        # State persistence.
        self._p_save = patch("monitor.run.save_state")
        self.mock_save = self._p_save.start()

        # Telegram helpers.
        self._p_send = patch("monitor.notify.send_message", return_value=True)
        self.mock_send = self._p_send.start()

        self._p_notify = patch("monitor.notify.notify_events")
        self.mock_notify_events = self._p_notify.start()

        # Sheets POST (rows_from_results runs for real).
        self._p_post = patch("monitor.sheets.post_rows", return_value=True)
        self.mock_post_rows = self._p_post.start()

    def tearDown(self):
        self._p_exit.stop()
        self._p_argv.stop()
        self._p_cfg.stop()
        self._p_state.stop()
        self._p_fetch.stop()
        self._p_save.stop()
        self._p_send.stop()
        self._p_notify.stop()
        self._p_post.stop()


# ---------------------------------------------------------------------------
# Seed path
# ---------------------------------------------------------------------------

class TestSeedPath(_RunTestBase):
    """Blank state -> seed run: one message, full snapshot, no per-product flood."""

    # Default setUp already provides blank state and 3-product results.

    def _run(self):
        from monitor.run import main
        main()

    def test_exactly_one_send_message(self):
        self._run()
        self.assertEqual(
            self.mock_send.call_count, 1,
            "Seed run must send exactly one channel message, not one per product.",
        )

    def test_message_contains_live_text(self):
        self._run()
        msg = self.mock_send.call_args[0][0]
        self.assertIn("PriceWatch is live", msg)

    def test_message_contains_product_count(self):
        self._run()
        msg = self.mock_send.call_args[0][0]
        self.assertIn("3", msg)

    def test_message_contains_store_count(self):
        self._run()
        msg = self.mock_send.call_args[0][0]
        self.assertIn("1", msg)  # one store (teststore)

    def test_notify_events_not_called_on_seed(self):
        self._run()
        self.mock_notify_events.assert_not_called()

    def test_full_snapshot_posted_to_sheets(self):
        self._run()
        self.mock_post_rows.assert_called_once()
        rows = self.mock_post_rows.call_args[0][0]
        # 3 products x 1 store = 3 rows.
        self.assertEqual(len(rows), 3)

    def test_state_saved_on_seed(self):
        self._run()
        self.mock_save.assert_called_once()

    def test_singular_product_word(self):
        """'1 product' not '1 products'."""
        self.mock_fetch.return_value = (_make_results(1), {})
        self._run()
        msg = self.mock_send.call_args[0][0]
        self.assertIn("1 product", msg)
        self.assertNotIn("1 products", msg)

    def test_plural_products_word(self):
        self._run()
        msg = self.mock_send.call_args[0][0]
        self.assertIn("3 products", msg)


# ---------------------------------------------------------------------------
# Normal path — changes present
# ---------------------------------------------------------------------------

class TestNormalPathWithChanges(_RunTestBase):
    """Prior state has one lower price -> one price_change event."""

    def setUp(self):
        super().setUp()
        prior = _seeded_state()
        # Set prod-a's prior price lower than the fetched 10000 -> price increase event.
        prior["items"]["prod-a"]["teststore"]["price"] = 9000
        self.mock_load_state.return_value = prior

    def _run(self):
        from monitor.run import main
        main()

    def test_notify_events_called(self):
        self._run()
        self.mock_notify_events.assert_called_once()

    def test_notify_events_receives_price_change(self):
        self._run()
        events = self.mock_notify_events.call_args[0][0]
        types = [e["type"] for e in events]
        self.assertIn("price_change", types)

    def test_no_seed_message_on_normal_run(self):
        """send_message is only called on seed; normal path uses notify_events."""
        self._run()
        self.mock_send.assert_not_called()

    def test_only_changed_row_posted_to_sheets(self):
        self._run()
        self.mock_post_rows.assert_called_once()
        rows = self.mock_post_rows.call_args[0][0]
        # Only the 1 changed product/store pair should be posted.
        self.assertEqual(len(rows), 1)

    def test_posted_row_is_for_changed_product(self):
        self._run()
        rows = self.mock_post_rows.call_args[0][0]
        # Column order: [checked_at, store, product_id, name, price, in_stock]
        self.assertEqual(rows[0][2], "prod-a")

    def test_state_saved(self):
        self._run()
        self.mock_save.assert_called_once()


# ---------------------------------------------------------------------------
# Normal path — no changes
# ---------------------------------------------------------------------------

class TestNormalPathNoChanges(_RunTestBase):
    """Prior state matches results exactly — no events, no Sheets post."""

    def setUp(self):
        super().setUp()
        self.mock_load_state.return_value = _seeded_state()

    def _run(self):
        from monitor.run import main
        main()

    def test_notify_events_not_called(self):
        self._run()
        self.mock_notify_events.assert_not_called()

    def test_no_sheets_post_when_no_changes(self):
        self._run()
        self.mock_post_rows.assert_not_called()

    def test_state_still_saved(self):
        self._run()
        self.mock_save.assert_called_once()


# ---------------------------------------------------------------------------
# Exit code
# ---------------------------------------------------------------------------

class TestExitCode(_RunTestBase):
    """Exit 1 when strictly >50% of attempts failed; exit 0 otherwise."""

    def _configure(self, n_ok: int, n_fail: int):
        """Set fetch_all return value to *n_ok* successes and *n_fail* failures."""
        results = {
            f"prod-ok-{i}": {
                "teststore": {"price": 1000, "in_stock": True, "name": f"OK {i}"}
            }
            for i in range(n_ok)
        }
        failures = {f"prod-fail-{i}": ["teststore"] for i in range(n_fail)}
        self.mock_fetch.return_value = (results, failures)

    def _run(self):
        from monitor.run import main
        main()

    def test_over_50pct_failure_exits_1(self):
        # 2 ok, 3 fail -> 60% failure rate.
        self._configure(n_ok=2, n_fail=3)
        self._run()
        self.mock_exit.assert_called_once_with(1)

    def test_exactly_50pct_failure_no_exit(self):
        # 3 ok, 3 fail -> exactly 50%; NOT strictly > 50% -> exit 0.
        self._configure(n_ok=3, n_fail=3)
        self._run()
        self.mock_exit.assert_not_called()

    def test_40pct_failure_no_exit(self):
        # 3 ok, 2 fail -> 40% failure rate.
        self._configure(n_ok=3, n_fail=2)
        self._run()
        self.mock_exit.assert_not_called()

    def test_zero_failures_no_exit(self):
        self._configure(n_ok=3, n_fail=0)
        self._run()
        self.mock_exit.assert_not_called()

    def test_all_failed_exits_1(self):
        # 0 ok, 5 fail -> 100% failure rate.
        self._configure(n_ok=0, n_fail=5)
        self._run()
        self.mock_exit.assert_called_once_with(1)

    def test_single_ok_single_fail_no_exit(self):
        # 1 ok, 1 fail -> 50% failure rate -> exit 0.
        self._configure(n_ok=1, n_fail=1)
        self._run()
        self.mock_exit.assert_not_called()

    def test_one_ok_two_fail_exits_1(self):
        # 1 ok, 2 fail -> 66.7% failure rate.
        self._configure(n_ok=1, n_fail=2)
        self._run()
        self.mock_exit.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

class TestDryRun(_RunTestBase):
    """--dry-run: fetch and diff happen; nothing is written or sent."""

    def setUp(self):
        super().setUp()
        self._p_argv.stop()
        self._p_argv = patch.object(sys, "argv", ["monitor.run", "--dry-run"])
        self._p_argv.start()

    def _run(self):
        from monitor.run import main
        main()

    def test_save_state_not_called(self):
        self._run()
        self.mock_save.assert_not_called()

    def test_send_message_not_called(self):
        """Seed path: no message sent in dry-run."""
        self._run()
        self.mock_send.assert_not_called()

    def test_post_rows_not_called(self):
        self._run()
        self.mock_post_rows.assert_not_called()

    def test_notify_events_not_called_on_seed_dry_run(self):
        self._run()
        self.mock_notify_events.assert_not_called()

    def test_normal_path_no_notify_events_in_dry_run(self):
        """Normal run with a change in dry-run mode: notify_events not called."""
        prior = _seeded_state()
        prior["items"]["prod-a"]["teststore"]["price"] = 9000
        self.mock_load_state.return_value = prior
        self._run()
        self.mock_notify_events.assert_not_called()

    def test_normal_path_no_post_rows_in_dry_run(self):
        prior = _seeded_state()
        prior["items"]["prod-a"]["teststore"]["price"] = 9000
        self.mock_load_state.return_value = prior
        self._run()
        self.mock_post_rows.assert_not_called()


if __name__ == "__main__":
    unittest.main()
