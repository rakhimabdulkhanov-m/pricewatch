"""Unit tests for monitor.sheets.

Covers:
- rows_from_results: column order, empty input, multiple products/stores.
- post_rows: success path, HTTP error body, network exception, missing env var.
- get_history: success path, network exception, missing env var.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# rows_from_results
# ---------------------------------------------------------------------------

class TestRowsFromResults(unittest.TestCase):

    def _make_results(self):
        return {
            "iphone-15-128": {
                "comfy": {"price": 32999, "in_stock": True,  "name": "iPhone 15 128GB"},
                "rozetka": {"price": 33500, "in_stock": False, "name": "iPhone 15 128GB"},
            },
            "samsung-s24": {
                "comfy": {"price": 27000, "in_stock": True, "name": "Samsung S24"},
            },
        }

    def test_returns_list(self):
        from monitor.sheets import rows_from_results
        rows = rows_from_results({}, "2026-07-17T10:00:00Z")
        self.assertIsInstance(rows, list)

    def test_empty_results_returns_empty(self):
        from monitor.sheets import rows_from_results
        self.assertEqual(rows_from_results({}, "2026-07-17T10:00:00Z"), [])

    def test_row_count_matches_product_store_pairs(self):
        from monitor.sheets import rows_from_results
        rows = rows_from_results(self._make_results(), "2026-07-17T10:00:00Z")
        self.assertEqual(len(rows), 3)

    def test_column_order(self):
        # Column order: [checked_at_utc, store, product_id, name, price_uah, in_stock]
        from monitor.sheets import rows_from_results
        results = {
            "my-product": {
                "teststore": {"price": 9999, "in_stock": True, "name": "My Product"},
            }
        }
        ts = "2026-07-17T12:34:56Z"
        rows = rows_from_results(results, ts)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row), 6)
        self.assertEqual(row[0], ts)           # checked_at_utc
        self.assertEqual(row[1], "teststore")  # store
        self.assertEqual(row[2], "my-product") # product_id
        self.assertEqual(row[3], "My Product") # name
        self.assertEqual(row[4], 9999)         # price_uah
        self.assertEqual(row[5], True)         # in_stock

    def test_timestamp_propagated_to_all_rows(self):
        from monitor.sheets import rows_from_results
        ts = "2026-07-17T09:00:00Z"
        rows = rows_from_results(self._make_results(), ts)
        for row in rows:
            self.assertEqual(row[0], ts)

    def test_out_of_stock_preserved(self):
        from monitor.sheets import rows_from_results
        results = {
            "prod": {
                "store": {"price": 1000, "in_stock": False, "name": "P"},
            }
        }
        row = rows_from_results(results, "2026-07-17T00:00:00Z")[0]
        self.assertFalse(row[5])

    def test_price_type_preserved(self):
        from monitor.sheets import rows_from_results
        results = {
            "prod": {
                "store": {"price": 12345, "in_stock": True, "name": "P"},
            }
        }
        row = rows_from_results(results, "2026-07-17T00:00:00Z")[0]
        self.assertIsInstance(row[4], int)


# ---------------------------------------------------------------------------
# post_rows
# ---------------------------------------------------------------------------

def _make_ok_response(appended=2):
    mock = MagicMock()
    mock.json.return_value = {"ok": True, "appended": appended}
    return mock


def _make_error_response(msg="script error"):
    mock = MagicMock()
    mock.json.return_value = {"ok": False, "error": msg}
    return mock


SAMPLE_ROWS = [
    ["2026-07-17T10:00:00Z", "comfy", "iphone-15-128", "iPhone 15", 32999, True],
    ["2026-07-17T10:00:00Z", "rozetka", "iphone-15-128", "iPhone 15", 33500, False],
]


class TestPostRows(unittest.TestCase):

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.post", return_value=_make_ok_response(2))
    def test_success_returns_true(self, mock_post):
        from monitor.sheets import post_rows
        result = post_rows(SAMPLE_ROWS)
        self.assertTrue(result)

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.post", return_value=_make_ok_response(2))
    def test_posts_to_webhook_url(self, mock_post):
        from monitor.sheets import post_rows
        post_rows(SAMPLE_ROWS)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://script.example.com/exec")

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.post", return_value=_make_ok_response(2))
    def test_sends_rows_in_body(self, mock_post):
        from monitor.sheets import post_rows
        post_rows(SAMPLE_ROWS)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"], {"rows": SAMPLE_ROWS})

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.post", return_value=_make_ok_response(2))
    def test_follow_redirects_enabled(self, mock_post):
        from monitor.sheets import post_rows
        post_rows(SAMPLE_ROWS)
        _, kwargs = mock_post.call_args
        self.assertTrue(kwargs.get("follow_redirects"))

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.post", return_value=_make_error_response("Apps Script error"))
    def test_api_error_returns_false(self, mock_post):
        from monitor.sheets import post_rows
        result = post_rows(SAMPLE_ROWS)
        self.assertFalse(result)

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.post", side_effect=Exception("Connection refused"))
    def test_network_exception_returns_false(self, mock_post):
        from monitor.sheets import post_rows
        result = post_rows(SAMPLE_ROWS)
        self.assertFalse(result)

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.post", side_effect=Exception("timeout"))
    def test_network_exception_does_not_raise(self, mock_post):
        from monitor.sheets import post_rows
        # Must not propagate the exception.
        try:
            post_rows(SAMPLE_ROWS)
        except Exception as exc:
            self.fail(f"post_rows raised unexpectedly: {exc}")

    def test_missing_env_var_returns_false(self):
        # Remove the env var entirely.
        env = {k: v for k, v in __import__("os").environ.items()
               if k != "SHEETS_WEBHOOK_URL"}
        with patch.dict("os.environ", env, clear=True):
            from monitor.sheets import post_rows
            result = post_rows(SAMPLE_ROWS)
            self.assertFalse(result)

    def test_missing_env_var_prints_to_stderr(self):
        env = {k: v for k, v in __import__("os").environ.items()
               if k != "SHEETS_WEBHOOK_URL"}
        with patch.dict("os.environ", env, clear=True):
            from monitor.sheets import post_rows
            import io
            buf = io.StringIO()
            with patch("sys.stderr", buf):
                post_rows(SAMPLE_ROWS)
            self.assertIn("SHEETS_WEBHOOK_URL", buf.getvalue())


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------

SAMPLE_HISTORY = [
    {"checked_at_utc": "2026-07-17T10:00:00Z", "store": "comfy",
     "product_id": "iphone-15-128", "name": "iPhone 15", "price_uah": 32999, "in_stock": True},
]


def _make_history_response():
    mock = MagicMock()
    mock.json.return_value = SAMPLE_HISTORY
    return mock


class TestGetHistory(unittest.TestCase):

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.get", return_value=_make_history_response())
    def test_success_returns_list(self, mock_get):
        from monitor.sheets import get_history
        result = get_history(days=30)
        self.assertEqual(result, SAMPLE_HISTORY)

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.get", return_value=_make_history_response())
    def test_passes_days_param(self, mock_get):
        from monitor.sheets import get_history
        get_history(days=7)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"], {"days": 7})

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.get", return_value=_make_history_response())
    def test_follow_redirects_enabled(self, mock_get):
        from monitor.sheets import get_history
        get_history()
        _, kwargs = mock_get.call_args
        self.assertTrue(kwargs.get("follow_redirects"))

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.get", side_effect=Exception("timeout"))
    def test_network_exception_returns_none(self, mock_get):
        from monitor.sheets import get_history
        result = get_history()
        self.assertIsNone(result)

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.get", side_effect=Exception("timeout"))
    def test_network_exception_does_not_raise(self, mock_get):
        from monitor.sheets import get_history
        try:
            get_history()
        except Exception as exc:
            self.fail(f"get_history raised unexpectedly: {exc}")

    def test_missing_env_var_returns_none(self):
        env = {k: v for k, v in __import__("os").environ.items()
               if k != "SHEETS_WEBHOOK_URL"}
        with patch.dict("os.environ", env, clear=True):
            from monitor.sheets import get_history
            result = get_history()
            self.assertIsNone(result)

    @patch.dict("os.environ", {"SHEETS_WEBHOOK_URL": "https://script.example.com/exec"})
    @patch("httpx.get", return_value=_make_history_response())
    def test_default_days_is_30(self, mock_get):
        from monitor.sheets import get_history
        get_history()
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["days"], 30)


if __name__ == "__main__":
    unittest.main()
