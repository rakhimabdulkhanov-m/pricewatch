"""Unit tests for the Rozetka store adapter.

The Cloudflare/TLS layer lives in monitor.http.fetch_page_impersonate and is
patched out here — these tests cover the adapter's own logic: JSON-LD wiring,
the product-URL redirect guard, and the FetchError paths. The parse itself is
monitor.jsonld (covered by test_jsonld).
"""

import unittest
from unittest.mock import patch

from monitor.stores.base import FetchError
from monitor.stores.rozetka import RozetkaAdapter

PRODUCT_URL = "https://rozetka.com.ua/ua/some-phone/p570541936/"
CATEGORY_URL = "https://rozetka.com.ua/ua/mobile-phones/c80003/"

_LD = (
    '<script type="application/ld+json">'
    '{{"@type":"Product","name":"Test Phone",'
    '"offers":{{"@type":"Offer","price":{price},'
    '"priceCurrency":"UAH"{avail}}}}}'
    "</script>"
)


def _html(price="65299", avail=', "availability":"https://schema.org/InStock"'):
    body = _LD.format(price=price, avail=avail) if price is not None else \
        '<script type="application/ld+json">{"@type":"Product","name":"x"}</script>'
    return f"<html><head>{body}</head><body></body></html>"


class RozetkaAdapterTest(unittest.TestCase):
    def setUp(self):
        self.adapter = RozetkaAdapter()
        self.patcher = patch("monitor.stores.rozetka.fetch_page_impersonate")
        self.mock_fetch = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_happy_path(self):
        self.mock_fetch.return_value = (_html(), PRODUCT_URL)
        data = self.adapter.fetch_product(PRODUCT_URL)
        self.assertEqual(data["price"], 65299)
        self.assertTrue(data["in_stock"])
        self.assertEqual(data["name"], "Test Phone")

    def test_out_of_stock(self):
        self.mock_fetch.return_value = (
            _html(avail=', "availability":"https://schema.org/OutOfStock"'),
            PRODUCT_URL,
        )
        self.assertFalse(self.adapter.fetch_product(PRODUCT_URL)["in_stock"])

    def test_missing_availability_defaults_in_stock(self):
        self.mock_fetch.return_value = (_html(avail=""), PRODUCT_URL)
        self.assertTrue(self.adapter.fetch_product(PRODUCT_URL)["in_stock"])

    def test_redirect_to_category_raises(self):
        # Product gone -> Rozetka redirects to a listing; final URL has no /p<id>/.
        self.mock_fetch.return_value = (_html(), CATEGORY_URL)
        with self.assertRaises(FetchError):
            self.adapter.fetch_product(PRODUCT_URL)

    def test_no_jsonld_raises(self):
        self.mock_fetch.return_value = ("<html><body>nothing</body></html>", PRODUCT_URL)
        with self.assertRaises(FetchError):
            self.adapter.fetch_product(PRODUCT_URL)

    def test_no_price_raises(self):
        self.mock_fetch.return_value = (_html(price=None), PRODUCT_URL)
        with self.assertRaises(FetchError):
            self.adapter.fetch_product(PRODUCT_URL)


if __name__ == "__main__":
    unittest.main()
