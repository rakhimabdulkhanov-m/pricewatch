"""Unit tests for monitor.notify.

Covers:
- format_event: thin-space thousands, true minus U+2212, percent rounding,
  HTML escaping, up/down arrows, stock messages.
- notify_events: digest at >10 postable events, individual sends at <=10.
"""

import unittest
from unittest.mock import call, patch

from monitor.notify import format_event, notify_events

# Unicode constants matching the production module (explicit escapes to avoid
# any encoding ambiguity when the file is saved/read on different platforms).
THIN = " "   # THIN SPACE
MINUS = "−"  # MINUS SIGN
ARROW = "→"  # RIGHTWARDS ARROW
UAH = "₴"    # HRYVNIA SIGN


# ---------------------------------------------------------------------------
# Helpers to build minimal event dicts (with url already enriched, as
# notify_events does before calling format_event).
# ---------------------------------------------------------------------------

def _price_ev(old_price: int, new_price: int, name: str = "Test Product",
              store_id: str = "comfy",
              url: str = "https://example.com/product") -> dict:
    return {
        "type": "price_change",
        "product_id": "test-product",
        "store_id": store_id,
        "old_price": old_price,
        "new_price": new_price,
        "name": name,
        "url": url,
    }


def _stock_ev(new_in_stock: bool, name: str = "Test Product",
              store_id: str = "comfy",
              url: str = "https://example.com/product") -> dict:
    return {
        "type": "stock_change",
        "product_id": "test-product",
        "store_id": store_id,
        "old_in_stock": not new_in_stock,
        "new_in_stock": new_in_stock,
        "name": name,
        "url": url,
    }


def _warn_ev(store_id: str = "comfy", consecutive: int = 2) -> dict:
    return {
        "type": "fetch_warning",
        "product_id": "test-product",
        "store_id": store_id,
        "consecutive_failures": consecutive,
    }


# ---------------------------------------------------------------------------
# format_event — price_change
# ---------------------------------------------------------------------------

class TestFormatEventPriceDown(unittest.TestCase):
    """Price decrease: 32999 -> 31499 — the canonical spec example."""

    def setUp(self):
        self.ev = _price_ev(32999, 31499,
                            name="Apple iPhone 15 128GB",
                            store_id="comfy",
                            url="https://example.com/iphone")
        self.text = format_event(self.ev)

    def test_down_arrow(self):
        self.assertTrue(self.text.startswith("\U0001f53b"),
                        f"Expected 🔻 prefix, got: {self.text!r}")

    def test_product_name_in_bold(self):
        self.assertIn("<b>Apple iPhone 15 128GB</b>", self.text)

    def test_old_price_thin_space(self):
        # 32999 -> "32 999" with thin space
        self.assertIn(f"32{THIN}999", self.text)

    def test_new_price_thin_space(self):
        # 31499 -> "31 499" with thin space
        self.assertIn(f"31{THIN}499", self.text)

    def test_arrow_between_prices(self):
        self.assertIn(ARROW, self.text)

    def test_hryvnia_sign(self):
        self.assertIn(UAH, self.text)

    def test_true_minus_in_percent(self):
        # Percent = (31499-32999)/32999*100 = -4.545...% -> -4.5% displayed as −4.5%
        self.assertIn(f"{MINUS}4.5%", self.text)

    def test_no_regular_hyphen_as_minus_in_percent(self):
        # The percent part must use U+2212, not ASCII hyphen-minus.
        # The line with the store contains the pct; find it.
        lines = self.text.split("\n")
        price_line = [l for l in lines if "Comfy:" in l][0]
        # After the arrow, should not contain a raw hyphen in the pct part.
        pct_part = price_line.split("(")[1]  # e.g. "−4.5%)"
        self.assertNotIn("-", pct_part,
                         "ASCII hyphen found in percent — should use U+2212")

    def test_store_name_capitalized(self):
        self.assertIn("Comfy:", self.text)

    def test_product_link(self):
        self.assertIn('<a href="https://example.com/iphone">product page</a>',
                      self.text)


class TestFormatEventPriceUp(unittest.TestCase):
    """Price increase: 30000 -> 35000."""

    def setUp(self):
        self.ev = _price_ev(30000, 35000)
        self.text = format_event(self.ev)

    def test_up_arrow(self):
        self.assertTrue(self.text.startswith("\U0001f53a"),
                        f"Expected 🔺 prefix, got: {self.text!r}")

    def test_plus_sign_in_percent(self):
        self.assertIn("+16.7%", self.text)


class TestFormatEventPricePercentRounding(unittest.TestCase):
    """Percent must be rounded to exactly 1 decimal place."""

    def test_one_decimal_place_exact(self):
        # 10000 -> 10100 = +1.0%
        text = format_event(_price_ev(10000, 10100))
        self.assertIn("+1.0%", text)

    def test_one_decimal_place_rounded(self):
        # 10000 -> 11333 = +13.33% -> +13.3%
        text = format_event(_price_ev(10000, 11333))
        self.assertIn("+13.3%", text)

    def test_five_digit_price_thin_spaces(self):
        # 100000 -> "100 000"
        text = format_event(_price_ev(100000, 99000))
        self.assertIn(f"100{THIN}000", text)

    def test_six_digit_prices(self):
        # 1000000 -> "1 000 000"
        text = format_event(_price_ev(1000000, 999000))
        self.assertIn(f"1{THIN}000{THIN}000", text)


# ---------------------------------------------------------------------------
# format_event — HTML escaping
# ---------------------------------------------------------------------------

class TestHtmlEscaping(unittest.TestCase):
    """Store-sourced text must be HTML-escaped."""

    def test_angle_brackets_in_name(self):
        ev = _price_ev(1000, 900, name="<b>Broken</b> & Co")
        text = format_event(ev)
        self.assertIn("&lt;b&gt;Broken&lt;/b&gt; &amp; Co", text)
        # Raw < must not appear inside the bold tag payload.
        # (The <b> tags around the name are ours; the name itself is escaped.)
        self.assertNotIn("<b>Broken</b>", text)

    def test_ampersand_in_name(self):
        ev = _price_ev(1000, 900, name="Tom & Jerry")
        text = format_event(ev)
        self.assertIn("Tom &amp; Jerry", text)

    def test_url_with_ampersand_escaped(self):
        ev = _price_ev(1000, 900, url="https://example.com/?a=1&b=2")
        text = format_event(ev)
        self.assertIn("https://example.com/?a=1&amp;b=2", text)


# ---------------------------------------------------------------------------
# format_event — stock_change
# ---------------------------------------------------------------------------

class TestFormatEventStock(unittest.TestCase):

    def test_back_in_stock(self):
        text = format_event(_stock_ev(new_in_stock=True))
        self.assertTrue(text.startswith("\U0001f4e6"),
                        f"Expected 📦 prefix, got: {text!r}")
        self.assertIn("back in stock", text)

    def test_out_of_stock(self):
        text = format_event(_stock_ev(new_in_stock=False))
        self.assertIn("out of stock", text)
        self.assertNotIn("back in stock", text)

    def test_product_name_in_bold(self):
        text = format_event(_stock_ev(new_in_stock=True, name="Some Gadget"))
        self.assertIn("<b>Some Gadget</b>", text)

    def test_product_link_present(self):
        text = format_event(_stock_ev(new_in_stock=True))
        self.assertIn("product page", text)

    def test_stock_event_has_no_price_formatting(self):
        text = format_event(_stock_ev(new_in_stock=True))
        # No arrow between prices expected in a stock event.
        self.assertNotIn(ARROW, text)


# ---------------------------------------------------------------------------
# notify_events — digest threshold
# ---------------------------------------------------------------------------

def _make_price_events(n: int) -> list[dict]:
    """Return *n* minimal price_change events (without url, as diff() returns)."""
    return [
        {
            "type": "price_change",
            "product_id": f"prod-{i}",
            "store_id": "comfy",
            "old_price": 10000,
            "new_price": 9000,
            "name": f"Product {i}",
        }
        for i in range(n)
    ]


def _products_by_id(n: int) -> dict:
    return {
        f"prod-{i}": {"urls": {"comfy": f"https://example.com/prod-{i}"}}
        for i in range(n)
    }


class TestNotifyEventsDigestThreshold(unittest.TestCase):
    """Digest fires when postable events > 10; individual sends for <= 10."""

    @patch("monitor.notify.send_message", return_value=True)
    @patch("monitor.notify.time")  # prevent real sleep
    def test_exactly_10_events_no_digest(self, mock_time, mock_send):
        events = _make_price_events(10)
        notify_events(events, _products_by_id(10))
        self.assertEqual(mock_send.call_count, 10,
                         "Expected 10 individual send_message calls for 10 events")

    @patch("monitor.notify.send_message", return_value=True)
    @patch("monitor.notify.time")
    def test_11_events_digest(self, mock_time, mock_send):
        events = _make_price_events(11)
        notify_events(events, _products_by_id(11))
        self.assertEqual(mock_send.call_count, 1,
                         "Expected 1 digest send_message call for 11 events")

    @patch("monitor.notify.send_message", return_value=True)
    @patch("monitor.notify.time")
    def test_digest_content_has_count_header(self, mock_time, mock_send):
        events = _make_price_events(11)
        notify_events(events, _products_by_id(11))
        digest_text = mock_send.call_args[0][0]
        self.assertIn("11 price/stock changes this run", digest_text)

    @patch("monitor.notify.send_message", return_value=True)
    @patch("monitor.notify.time")
    def test_fetch_warnings_not_counted_toward_threshold(self, mock_time, mock_send):
        # 10 price events + 5 fetch_warning events -> still individual sends (10, not 15)
        events = _make_price_events(10) + [_warn_ev(store_id=f"store-{i}") for i in range(5)]
        notify_events(events, _products_by_id(10))
        self.assertEqual(mock_send.call_count, 10)

    @patch("monitor.notify.send_message", return_value=True)
    @patch("monitor.notify.time")
    def test_fetch_warnings_only_no_send(self, mock_time, mock_send):
        events = [_warn_ev(store_id=f"store-{i}") for i in range(5)]
        notify_events(events, {})
        mock_send.assert_not_called()

    @patch("monitor.notify.send_message", return_value=True)
    @patch("monitor.notify.time")
    def test_individual_sends_use_sleep_between(self, mock_time, mock_send):
        events = _make_price_events(3)
        notify_events(events, _products_by_id(3))
        # time.sleep should be called n-1 times (between sends, not before first).
        self.assertEqual(mock_time.sleep.call_count, 2)
        mock_time.sleep.assert_called_with(1)

    @patch("monitor.notify.send_message", return_value=True)
    @patch("monitor.notify.time")
    def test_digest_no_sleep_between_events(self, mock_time, mock_send):
        events = _make_price_events(15)
        notify_events(events, _products_by_id(15))
        # Digest path: one send, no sleep calls (sleep is only on individual path).
        mock_time.sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
