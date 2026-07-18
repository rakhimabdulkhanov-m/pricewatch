"""Tests for monitor.report and monitor.chartstyle.

Covers:
- Number formatting: thin space, true minus, rounding
- Percent-axis formatter
- Short name truncation
- Top-mover selection ordering
- Locale dict completeness (every key present in both en and uk)
- Month abbreviation dict completeness (12 months, both locales)
- Caption HTML-safety
- <7-day degradation path (title says 'first N days')
- Locale-aware date formatting (uk: Ukrainian month abbreviations)
- Chart generation (smoke test): en + uk PNGs are written and non-empty
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

# ---------------------------------------------------------------------------
# Synthetic 7-day fixture
# ---------------------------------------------------------------------------
# Several products x 2 stores, realistic UAH prices, a few drops/rises,
# one stock flip (stock field present but not driving the chart).

_DAY = "2026-07-{:02d}T10:00:00Z"


def _row(day: int, product_id: str, store: str, name: str,
         price: float, in_stock: bool = True) -> dict:
    return {
        "checked_at_utc": _DAY.format(day + 11),  # 2026-07-11 .. 2026-07-17
        "store": store,
        "product_id": product_id,
        "name": name,
        "price_uah": float(price),
        "in_stock": in_stock,
    }


# Product A — Apple iPhone 15 128GB: drops ~5% at moyo
_IPHONE_MOYO = [
    _row(0, "iphone-15", "moyo", "Apple iPhone 15 128GB", 32999),
    _row(1, "iphone-15", "moyo", "Apple iPhone 15 128GB", 32999),
    _row(2, "iphone-15", "moyo", "Apple iPhone 15 128GB", 31499),
    _row(3, "iphone-15", "moyo", "Apple iPhone 15 128GB", 31499),
    _row(4, "iphone-15", "moyo", "Apple iPhone 15 128GB", 31499),
    _row(5, "iphone-15", "moyo", "Apple iPhone 15 128GB", 31299),
    _row(6, "iphone-15", "moyo", "Apple iPhone 15 128GB", 31299),
]

# Product A — same product, comfy store: slight rise
_IPHONE_COMFY = [
    _row(0, "iphone-15", "comfy", "Apple iPhone 15 128GB", 33500),
    _row(2, "iphone-15", "comfy", "Apple iPhone 15 128GB", 33500),
    _row(4, "iphone-15", "comfy", "Apple iPhone 15 128GB", 34200),
    _row(6, "iphone-15", "comfy", "Apple iPhone 15 128GB", 34200),
]

# Product B — Samsung TV 55": big drop
_TV_MOYO = [
    _row(0, "samsung-tv-55", "moyo", 'Samsung TV 55" 4K', 25000),
    _row(2, "samsung-tv-55", "moyo", 'Samsung TV 55" 4K', 23500),
    _row(4, "samsung-tv-55", "moyo", 'Samsung TV 55" 4K', 22000),
    _row(6, "samsung-tv-55", "moyo", 'Samsung TV 55" 4K', 22000),
]

# Product B — comfy: stable
_TV_COMFY = [
    _row(0, "samsung-tv-55", "comfy", 'Samsung TV 55" 4K', 26000),
    _row(3, "samsung-tv-55", "comfy", 'Samsung TV 55" 4K', 26000),
    _row(6, "samsung-tv-55", "comfy", 'Samsung TV 55" 4K', 26000),
]

# Product C — Sony Headphones: price rise, stock flip (out -> in)
_SONY_MOYO = [
    _row(0, "sony-wh1000xm5", "moyo", "Sony WH-1000XM5", 9999, in_stock=False),
    _row(2, "sony-wh1000xm5", "moyo", "Sony WH-1000XM5", 9999, in_stock=True),
    _row(4, "sony-wh1000xm5", "moyo", "Sony WH-1000XM5", 10999, in_stock=True),
    _row(6, "sony-wh1000xm5", "moyo", "Sony WH-1000XM5", 10999, in_stock=True),
]

# Product D — Dyson V15: moderate drop
_DYSON_COMFY = [
    _row(0, "dyson-v15", "comfy", "Dyson V15 Detect", 19999),
    _row(2, "dyson-v15", "comfy", "Dyson V15 Detect", 19999),
    _row(5, "dyson-v15", "comfy", "Dyson V15 Detect", 17999),
    _row(6, "dyson-v15", "comfy", "Dyson V15 Detect", 17999),
]

# Product E — Nespresso: small rise (stable-ish)
_NESPRESSO_MOYO = [
    _row(0, "nespresso-vertuo", "moyo", "Nespresso Vertuo Pop", 3999),
    _row(3, "nespresso-vertuo", "moyo", "Nespresso Vertuo Pop", 3999),
    _row(6, "nespresso-vertuo", "moyo", "Nespresso Vertuo Pop", 4199),
    # day=7 → 2026-07-18: extends the window to a genuine 7-day span so the
    # full "11 Jul – 18 Jul" header fires and locale date tests are meaningful.
    _row(7, "nespresso-vertuo", "moyo", "Nespresso Vertuo Pop", 4199),
]

FIXTURE_7D: list[dict] = (
    _IPHONE_MOYO + _IPHONE_COMFY
    + _TV_MOYO + _TV_COMFY
    + _SONY_MOYO
    + _DYSON_COMFY
    + _NESPRESSO_MOYO
)

# Sub-7-day fixture (3 days)
FIXTURE_3D: list[dict] = [
    r for r in FIXTURE_7D
    if r["checked_at_utc"] >= "2026-07-11"
    and r["checked_at_utc"] <= "2026-07-13T23:59:59Z"
]


# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from monitor.report import (
    fmt_price,
    fmt_pct,
    _fmt_pct_axis,
    _short_name,
    weekly_caption,
    build_chart,
    _parse_ts,
    _build_series,
    _select_top_movers,
    _top_moves_rows,
    _LOCALE,
    _MONTHS,
    _months,
)
from monitor import chartstyle

# Unicode constants (explicit codepoints to avoid any encoding ambiguity)
THIN = " "   # THIN SPACE
MINUS = "−"  # MINUS SIGN


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------

class TestFmtPrice(unittest.TestCase):
    """Thin-space thousands separator, integer rounding."""

    def test_four_digit(self):
        self.assertEqual(fmt_price(9999), "9 999")

    def test_five_digit(self):
        self.assertEqual(fmt_price(31499), "31 499")

    def test_six_digit(self):
        self.assertEqual(fmt_price(100000), "100 000")

    def test_seven_digit(self):
        self.assertEqual(fmt_price(1000000), "1 000 000")

    def test_three_digit(self):
        self.assertEqual(fmt_price(999), "999")

    def test_rounding_float(self):
        # 31499.6 -> rounds to 31500
        self.assertEqual(fmt_price(31499.6), "31 500")

    def test_thin_space_is_u2009(self):
        result = fmt_price(32999)
        self.assertIn(THIN, result)
        self.assertEqual(result, f"32{THIN}999")


class TestFmtPct(unittest.TestCase):
    """True minus for negative, + for positive, 1 decimal place."""

    def test_drop_canonical(self):
        # 32999 -> 31499: -4.545...% -> minus 4.5%
        result = fmt_pct(32999, 31499)
        self.assertEqual(result, f"{MINUS}4.5%")

    def test_true_minus_not_hyphen(self):
        result = fmt_pct(10000, 9000)
        self.assertTrue(result.startswith(MINUS),
                        f"Expected U+2212 prefix, got: {result!r}")
        self.assertNotIn("-", result, "ASCII hyphen found — must use U+2212")

    def test_rise(self):
        result = fmt_pct(30000, 35000)
        self.assertEqual(result, "+16.7%")

    def test_one_decimal_exact(self):
        result = fmt_pct(10000, 10100)
        self.assertEqual(result, "+1.0%")

    def test_one_decimal_rounded(self):
        result = fmt_pct(10000, 11333)
        self.assertEqual(result, "+13.3%")

    def test_negative_rounded(self):
        result = fmt_pct(10000, 8999)
        self.assertEqual(result, f"{MINUS}10.0%")


class TestFmtPctAxis(unittest.TestCase):
    """Y-axis percent formatter (percent-change mode)."""

    def test_zero(self):
        self.assertEqual(_fmt_pct_axis(0, None), "0%")

    def test_positive(self):
        self.assertEqual(_fmt_pct_axis(5.0, None), "+5.0%")

    def test_negative_uses_true_minus(self):
        result = _fmt_pct_axis(-12.0, None)
        self.assertTrue(result.startswith(MINUS),
                        f"Expected true minus prefix, got {result!r}")
        self.assertNotIn("-", result)

    def test_negative_value(self):
        result = _fmt_pct_axis(-4.5, None)
        self.assertEqual(result, f"{MINUS}4.5%")


class TestShortName(unittest.TestCase):
    """Name truncation to max 18 chars."""

    def test_short_name_unchanged(self):
        self.assertEqual(_short_name("Dyson V15 Detect"), "Dyson V15 Detect")

    def test_exactly_18_chars_unchanged(self):
        name = "A" * 18
        self.assertEqual(_short_name(name), name)

    def test_19_chars_truncated(self):
        name = "A" * 19
        result = _short_name(name)
        self.assertEqual(len(result), 18)  # 17 chars + ellipsis
        self.assertTrue(result.endswith("…"), "Must end with ellipsis")

    def test_long_name(self):
        name = "Apple iPhone 15 128GB"  # 21 chars
        result = _short_name(name)
        self.assertLessEqual(len(result), 18)
        self.assertTrue(result.endswith("…"))

    def test_custom_max(self):
        result = _short_name("Hello World", max_chars=8)
        self.assertEqual(len(result), 8)
        self.assertTrue(result.endswith("…"))


# ---------------------------------------------------------------------------
# Top-mover selection
# ---------------------------------------------------------------------------

class TestTopMovers(unittest.TestCase):

    def setUp(self):
        self.series = _build_series(FIXTURE_7D)

    def test_returns_at_most_6(self):
        keys = _select_top_movers(self.series, n=6)
        self.assertLessEqual(len(keys), 6)

    def test_returns_at_least_4_when_enough_data(self):
        keys = _select_top_movers(self.series, n=5)
        self.assertGreaterEqual(len(keys), 4)

    def test_first_mover_has_highest_abs_change(self):
        keys = _select_top_movers(self.series, n=5)
        from monitor.report import _pct_change
        top_change = _pct_change(self.series[keys[0]])
        for k in keys[1:]:
            self.assertGreaterEqual(
                top_change, _pct_change(self.series[k]) - 0.001,
                "First mover should have the highest absolute percent change",
            )

    def test_ordering_descending(self):
        keys = _select_top_movers(self.series, n=6)
        from monitor.report import _pct_change
        changes = [_pct_change(self.series[k]) for k in keys]
        self.assertEqual(changes, sorted(changes, reverse=True))


# ---------------------------------------------------------------------------
# Locale dict completeness
# ---------------------------------------------------------------------------

class TestLocaleCompleteness(unittest.TestCase):
    """Every key present in both 'en' and 'uk' dicts."""

    def test_all_en_keys_in_uk(self):
        en_keys = set(_LOCALE["en"].keys())
        uk_keys = set(_LOCALE["uk"].keys())
        missing = en_keys - uk_keys
        self.assertFalse(missing, f"Keys in 'en' but missing from 'uk': {missing}")

    def test_all_uk_keys_in_en(self):
        en_keys = set(_LOCALE["en"].keys())
        uk_keys = set(_LOCALE["uk"].keys())
        missing = uk_keys - en_keys
        self.assertFalse(missing, f"Keys in 'uk' but missing from 'en': {missing}")

    def test_en_values_non_empty(self):
        for k, v in _LOCALE["en"].items():
            self.assertTrue(v, f"Empty value for key '{k}' in 'en'")

    def test_uk_values_non_empty(self):
        for k, v in _LOCALE["uk"].items():
            self.assertTrue(v, f"Empty value for key '{k}' in 'uk'")


# ---------------------------------------------------------------------------
# Month abbreviation dict completeness
# ---------------------------------------------------------------------------

class TestMonthsCompleteness(unittest.TestCase):
    """Both locale month lists must have exactly 12 entries."""

    def test_en_has_12_months(self):
        self.assertEqual(len(_MONTHS["en"]), 12)

    def test_uk_has_12_months(self):
        self.assertEqual(len(_MONTHS["uk"]), 12)

    def test_en_months_non_empty(self):
        for i, m in enumerate(_MONTHS["en"]):
            self.assertTrue(m, f"Empty month at index {i} in 'en'")

    def test_uk_months_non_empty(self):
        for i, m in enumerate(_MONTHS["uk"]):
            self.assertTrue(m, f"Empty month at index {i} in 'uk'")

    def test_uk_july_is_cyrillic(self):
        # July is month index 6; must be Ukrainian 'лип'
        self.assertEqual(_MONTHS["uk"][6], "лип")

    def test_months_helper_returns_uk(self):
        uk = _months("uk")
        self.assertEqual(uk[0], "січ")  # "січ"

    def test_months_helper_falls_back_to_en(self):
        fallback = _months("zz")  # unknown locale
        self.assertEqual(fallback, _MONTHS["en"])


# ---------------------------------------------------------------------------
# Caption HTML-safety
# ---------------------------------------------------------------------------

class TestCaptionHtmlSafety(unittest.TestCase):

    def test_no_raw_html_in_name(self):
        rows = [
            {
                "checked_at_utc": "2026-07-11T10:00:00Z",
                "store": "moyo",
                "product_id": "xss-prod",
                "name": "<script>alert(1)</script>",
                "price_uah": 10000.0,
                "in_stock": True,
            },
            {
                "checked_at_utc": "2026-07-17T10:00:00Z",
                "store": "moyo",
                "product_id": "xss-prod",
                "name": "<script>alert(1)</script>",
                "price_uah": 9000.0,
                "in_stock": True,
            },
        ]
        caption = weekly_caption(rows, locale="en")
        self.assertNotIn("<script>", caption)
        self.assertIn("&lt;script&gt;", caption)

    def test_ampersand_escaped(self):
        rows = [
            {
                "checked_at_utc": "2026-07-11T10:00:00Z",
                "store": "comfy",
                "product_id": "amp-prod",
                "name": "Tom & Jerry Edition",
                "price_uah": 5000.0,
                "in_stock": True,
            },
            {
                "checked_at_utc": "2026-07-17T10:00:00Z",
                "store": "comfy",
                "product_id": "amp-prod",
                "name": "Tom & Jerry Edition",
                "price_uah": 4500.0,
                "in_stock": True,
            },
        ]
        caption = weekly_caption(rows, locale="en")
        self.assertNotIn(" & ", caption)
        self.assertIn("&amp;", caption)

    def test_fixture_caption_has_bold_header(self):
        caption = weekly_caption(FIXTURE_7D, locale="en")
        self.assertIn("<b>", caption)
        self.assertIn("</b>", caption)

    def test_no_em_dash_in_caption(self):
        caption = weekly_caption(FIXTURE_7D, locale="en")
        self.assertNotIn("—", caption,
                         "Em dash found — must not appear in client-visible strings")

    def test_title_uses_middot_not_period(self):
        # Title: "PriceWatch · Weekly price report" (middot, not period)
        self.assertIn("·", _LOCALE["en"]["title"])
        self.assertNotIn("PriceWatch.", _LOCALE["en"]["title"])


# ---------------------------------------------------------------------------
# Degradation: < 7 days of data
# ---------------------------------------------------------------------------

class TestShortWindowDegradation(unittest.TestCase):

    def test_caption_says_first_n_days_en(self):
        caption = weekly_caption(FIXTURE_3D, locale="en")
        self.assertIn("first", caption.lower())

    def test_caption_says_first_n_days_uk(self):
        caption = weekly_caption(FIXTURE_3D, locale="uk")
        self.assertIn("перші", caption.lower())  # "перші"

    def test_chart_short_window_produces_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_short.png"
            result = build_chart(FIXTURE_3D, locale="en", out_path=out)
            self.assertTrue(result.exists(), "PNG file was not created")
            self.assertGreater(result.stat().st_size, 5000, "PNG too small")


# ---------------------------------------------------------------------------
# Locale-aware date formatting
# ---------------------------------------------------------------------------

class TestLocaleDates(unittest.TestCase):
    """UK chart must use Ukrainian month abbreviations on the x-axis."""

    def test_uk_caption_header_uses_ukrainian_month(self):
        # The 7-day fixture spans July; UK caption header should say 'лип'.
        caption = weekly_caption(FIXTURE_7D, locale="uk")
        self.assertIn("лип", caption,  # "лип"
                      "UK caption must use Ukrainian month abbreviation 'лип' for July")

    def test_en_caption_header_uses_en_month(self):
        caption = weekly_caption(FIXTURE_7D, locale="en")
        self.assertIn("Jul", caption)

    def test_months_july_index(self):
        # Sanity: months are 0-indexed, July is index 6.
        self.assertEqual(_MONTHS["en"][6], "Jul")
        self.assertEqual(_MONTHS["uk"][6], "лип")


# ---------------------------------------------------------------------------
# Chart generation smoke tests
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent.parent / "temp" / "output"


class TestChartGeneration(unittest.TestCase):
    """Generate en and uk PNGs from the 7-day fixture and verify file integrity."""

    @classmethod
    def setUpClass(cls):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.en_path = OUTPUT_DIR / "pricewatch_weekly_en.png"
        cls.uk_path = OUTPUT_DIR / "pricewatch_weekly_uk.png"
        cls.en_result = build_chart(FIXTURE_7D, locale="en", out_path=cls.en_path)
        cls.uk_result = build_chart(FIXTURE_7D, locale="uk", out_path=cls.uk_path)

    def test_en_png_exists(self):
        self.assertTrue(self.en_result.exists())

    def test_uk_png_exists(self):
        self.assertTrue(self.uk_result.exists())

    def test_en_png_non_empty(self):
        self.assertGreater(self.en_result.stat().st_size, 10_000)

    def test_uk_png_non_empty(self):
        self.assertGreater(self.uk_result.stat().st_size, 10_000)

    def test_en_is_valid_png(self):
        data = self.en_result.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")

    def test_uk_is_valid_png(self):
        data = self.uk_result.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")

    def test_en_png_dimensions(self):
        """PNG must be 1600x900 (8in x 4.5in at 200 DPI)."""
        import struct
        data = self.en_result.read_bytes()
        w = struct.unpack(">I", data[16:20])[0]
        h = struct.unpack(">I", data[20:24])[0]
        self.assertEqual(w, 1600, f"Expected 1600, got {w}")
        self.assertEqual(h, 900, f"Expected 900, got {h}")

    def test_uk_png_dimensions(self):
        import struct
        data = self.uk_result.read_bytes()
        w = struct.unpack(">I", data[16:20])[0]
        h = struct.unpack(">I", data[20:24])[0]
        self.assertEqual(w, 1600, f"Expected 1600, got {w}")
        self.assertEqual(h, 900, f"Expected 900, got {h}")

    def test_caption_en_has_thin_space(self):
        caption = weekly_caption(FIXTURE_7D, locale="en")
        self.assertIn(THIN, caption)

    def test_caption_en_has_true_minus(self):
        caption = weekly_caption(FIXTURE_7D, locale="en")
        self.assertIn(MINUS, caption)

    def test_output_paths(self):
        """Report absolute paths for the main session to inspect."""
        print(f"\n[test] EN PNG: {self.en_result.resolve()}")
        print(f"[test] UK PNG: {self.uk_result.resolve()}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
