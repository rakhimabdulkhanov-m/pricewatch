"""Unit tests for monitor.jsonld.extract_product.

Covers:
  - Top-level Product schema
  - @graph nesting (single and recursive)
  - JSON-LD block that is a bare array
  - Multiple blocks: first Product wins
  - Malformed JSON block skipped; next valid block used
  - offers as dict vs list (first offer with price)
  - Price: int, float, float-string, space-separated string
  - All schema.org availability forms (full URL https/http, bare value)
  - Unknown availability -> None
  - Missing availability -> None
"""

import json
import unittest

from monitor.jsonld import extract_product


# ---------------------------------------------------------------------------
# HTML fixture builder
# ---------------------------------------------------------------------------

def _html(*ld_objects) -> str:
    """Wrap each object as a separate application/ld+json block in minimal HTML."""
    scripts = "".join(
        f'<script type="application/ld+json">{json.dumps(obj)}</script>\n'
        for obj in ld_objects
    )
    return f"<html><head>{scripts}</head><body></body></html>"


def _html_raw(*raw_texts) -> str:
    """Wrap raw strings as ld+json blocks (allows injecting invalid JSON)."""
    scripts = "".join(
        f'<script type="application/ld+json">{t}</script>\n'
        for t in raw_texts
    )
    return f"<html><head>{scripts}</head><body></body></html>"


# ---------------------------------------------------------------------------
# Basic extraction
# ---------------------------------------------------------------------------

class TestBasic(unittest.TestCase):
    def test_top_level_product_returns_dict(self):
        html = _html({
            "@type": "Product",
            "name": "Test Phone",
            "offers": {
                "price": 12999,
                "availability": "https://schema.org/InStock",
            },
        })
        result = extract_product(html)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Test Phone")
        self.assertEqual(result["price"], 12999)
        self.assertTrue(result["in_stock"])

    def test_no_product_returns_none(self):
        html = _html({"@type": "WebPage", "name": "Some page"})
        self.assertIsNone(extract_product(html))

    def test_no_ld_json_blocks_returns_none(self):
        self.assertIsNone(extract_product("<html><body>plain page</body></html>"))

    def test_empty_html_returns_none(self):
        self.assertIsNone(extract_product(""))


# ---------------------------------------------------------------------------
# @graph nesting
# ---------------------------------------------------------------------------

class TestGraphNesting(unittest.TestCase):
    def test_product_in_top_level_graph(self):
        html = _html({
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebSite"},
                {
                    "@type": "Product",
                    "name": "Graph Phone",
                    "offers": {
                        "price": 24999,
                        "availability": "https://schema.org/InStock",
                    },
                },
            ],
        })
        result = extract_product(html)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Graph Phone")
        self.assertEqual(result["price"], 24999)
        self.assertTrue(result["in_stock"])

    def test_product_in_nested_graph(self):
        """Product found inside a @graph that is itself inside a @graph."""
        html = _html({
            "@graph": [
                {
                    "@graph": [
                        {
                            "@type": "Product",
                            "name": "Deep Product",
                            "offers": {"price": 5000, "availability": "OutOfStock"},
                        }
                    ]
                }
            ]
        })
        result = extract_product(html)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Deep Product")
        self.assertFalse(result["in_stock"])


# ---------------------------------------------------------------------------
# Array of objects as a JSON-LD block
# ---------------------------------------------------------------------------

class TestArrayBlock(unittest.TestCase):
    def test_product_in_array_block(self):
        """JSON-LD block is a JSON array; Product is found inside it."""
        html = _html(
            [
                {"@type": "BreadcrumbList"},
                {
                    "@type": "Product",
                    "name": "Array Block Product",
                    "offers": {"price": 19990, "availability": "InStock"},
                },
            ]
        )
        result = extract_product(html)
        self.assertIsNotNone(result)
        self.assertEqual(result["price"], 19990)

    def test_multiple_blocks_first_product_wins(self):
        """When multiple blocks each contain a Product, the one in the first block wins."""
        html = _html(
            {"@type": "WebSite"},
            {"@type": "Product", "name": "First", "offers": {"price": 1111, "availability": "InStock"}},
            {"@type": "Product", "name": "Second", "offers": {"price": 2222, "availability": "InStock"}},
        )
        result = extract_product(html)
        self.assertEqual(result["name"], "First")
        self.assertEqual(result["price"], 1111)


# ---------------------------------------------------------------------------
# Malformed JSON blocks
# ---------------------------------------------------------------------------

class TestMalformedJson(unittest.TestCase):
    def test_malformed_block_skipped_valid_block_used(self):
        """A malformed JSON block is skipped; the subsequent valid block is used."""
        good = json.dumps({
            "@type": "Product",
            "name": "Good Product",
            "offers": {"price": 7777, "availability": "InStock"},
        })
        html = _html_raw("{broken json", good)
        result = extract_product(html)
        self.assertIsNotNone(result)
        self.assertEqual(result["price"], 7777)

    def test_all_malformed_returns_none(self):
        html = _html_raw("{bad}", "not json at all!!")
        self.assertIsNone(extract_product(html))

    def test_empty_script_blocks_skipped(self):
        """Empty or whitespace-only script blocks are silently skipped."""
        good = json.dumps({
            "@type": "Product",
            "name": "P",
            "offers": {"price": 500, "availability": "InStock"},
        })
        html = _html_raw("", "   ", good)
        result = extract_product(html)
        self.assertIsNotNone(result)
        self.assertEqual(result["price"], 500)


# ---------------------------------------------------------------------------
# Price parsing
# ---------------------------------------------------------------------------

class TestPriceParsing(unittest.TestCase):
    def _price(self, price_val) -> int | None:
        result = extract_product(_html({
            "@type": "Product",
            "name": "P",
            "offers": {"price": price_val, "availability": "InStock"},
        }))
        return result["price"] if result else None

    def test_integer_price(self):
        self.assertEqual(self._price(32000), 32000)

    def test_float_rounds_half_up(self):
        # 12799.80 -> 12800
        self.assertEqual(self._price(12799.80), 12800)

    def test_float_truncates_when_below_half(self):
        # 12799.30 -> 12799
        self.assertEqual(self._price(12799.30), 12799)

    def test_float_string(self):
        # "9999.50" -> 10000
        self.assertEqual(self._price("9999.50"), 10000)

    def test_integer_string(self):
        self.assertEqual(self._price("12799"), 12799)

    def test_price_with_spaces(self):
        # "12 799" — space as thousands separator
        self.assertEqual(self._price("12 799"), 12799)

    def test_none_price_returns_none(self):
        self.assertIsNone(self._price(None))


# ---------------------------------------------------------------------------
# Offers as list
# ---------------------------------------------------------------------------

class TestOffersAsList(unittest.TestCase):
    def test_takes_first_offer_with_price(self):
        html = _html({
            "@type": "Product",
            "name": "Multi",
            "offers": [
                {"price": None, "availability": "InStock"},
                {"price": 9999, "availability": "InStock"},
                {"price": 8000, "availability": "InStock"},
            ],
        })
        result = extract_product(html)
        # First offer has price=None, so second (9999) is the first with a price.
        self.assertEqual(result["price"], 9999)

    def test_single_item_list(self):
        html = _html({
            "@type": "Product",
            "name": "Solo",
            "offers": [{"price": 15000, "availability": "PreOrder"}],
        })
        result = extract_product(html)
        self.assertEqual(result["price"], 15000)
        self.assertTrue(result["in_stock"])


# ---------------------------------------------------------------------------
# Availability forms
# ---------------------------------------------------------------------------

class TestAvailabilityForms(unittest.TestCase):
    def _in_stock(self, avail_value) -> bool | None:
        html = _html({
            "@type": "Product",
            "name": "T",
            "offers": {"price": 1000, "availability": avail_value},
        })
        result = extract_product(html)
        return result["in_stock"] if result else None

    # Full https URL
    def test_https_instock(self):
        self.assertTrue(self._in_stock("https://schema.org/InStock"))

    def test_https_outofstock(self):
        self.assertFalse(self._in_stock("https://schema.org/OutOfStock"))

    def test_https_preorder(self):
        self.assertTrue(self._in_stock("https://schema.org/PreOrder"))

    def test_https_discontinued(self):
        self.assertFalse(self._in_stock("https://schema.org/Discontinued"))

    # Full http URL
    def test_http_instock(self):
        self.assertTrue(self._in_stock("http://schema.org/InStock"))

    def test_http_outofstock(self):
        self.assertFalse(self._in_stock("http://schema.org/OutOfStock"))

    def test_http_preorder(self):
        self.assertTrue(self._in_stock("http://schema.org/PreOrder"))

    def test_http_discontinued(self):
        self.assertFalse(self._in_stock("http://schema.org/Discontinued"))

    # Bare values (no URL prefix)
    def test_bare_instock(self):
        self.assertTrue(self._in_stock("InStock"))

    def test_bare_outofstock(self):
        self.assertFalse(self._in_stock("OutOfStock"))

    def test_bare_preorder(self):
        self.assertTrue(self._in_stock("PreOrder"))

    def test_bare_discontinued(self):
        self.assertFalse(self._in_stock("Discontinued"))

    def test_unknown_value_returns_none(self):
        self.assertIsNone(self._in_stock("SomethingElse"))

    def test_missing_availability_returns_none(self):
        html = _html({
            "@type": "Product",
            "name": "No avail",
            "offers": {"price": 5000},
        })
        result = extract_product(html)
        self.assertIsNone(result["in_stock"])


if __name__ == "__main__":
    unittest.main()
