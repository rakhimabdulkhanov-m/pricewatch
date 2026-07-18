"""Store adapter for MOYO (moyo.ua).

MOYO product pages do not expose schema.org/Product via JSON-LD.
Price extraction order:
  1. Inline JS  — "price": N patterns inside <script> tags.
  2. data-price attribute — first data-price="N" on any element (main product).

Availability via Ukrainian text:
  "В наявності"  -> True
  "Відсутній"    -> False
  Neither found  -> True (with a stderr warning).

Product name from <h1>, falling back to og:title meta.

URL guard: MOYO redirects removed/discontinued products to category listings.
If the final URL after redirect does not end with /<numeric_id>.html the
product is gone and FetchError is raised.
"""

import re
import sys

from selectolax.parser import HTMLParser

from monitor.http import fetch_page
from monitor.stores.base import FetchError, StoreAdapter

# MOYO product pages end with a numeric ID before .html
_PRODUCT_URL_RE = re.compile(r"/\d+\.html(?:[?#].*)?$")

# Inline JSON price patterns (same selectors proven in scripts/actions_probe.py)
_EMBEDDED_PRICE_RE = re.compile(
    r'"(?:price|Price|currentPrice|salePrice|regularPrice)"\s*:\s*'
    r'(["\']?)(\d[\d. ]*)(?:\.\d+)?\1',
    re.IGNORECASE,
)
# data-price="12799" or data-price="12799.00"
_DATA_PRICE_RE = re.compile(r'data-price=["\']([0-9]+(?:\.[0-9]+)?)["\']', re.IGNORECASE)

# Range guard: UAH prices outside this range are likely parsing artefacts
_MIN_PRICE = 100
_MAX_PRICE = 1_000_000


def _parse_price(raw: str) -> int | None:
    """Strip non-numeric chars (except dot) from *raw* and return int UAH."""
    s = re.sub(r"[^\d.]", "", raw)
    if not s or s == ".":
        return None
    try:
        return round(float(s))
    except ValueError:
        return None


class MoyoAdapter(StoreAdapter):
    """Fetches price and availability from moyo.ua product pages."""

    def fetch_product(self, url: str) -> dict:
        html, final_url = fetch_page(url)

        # Guard: redirect to category page means product is gone.
        if not _PRODUCT_URL_RE.search(final_url):
            raise FetchError(
                f"MOYO: redirected to non-product URL {final_url!r} (original: {url!r})"
            )

        tree = HTMLParser(html)

        # --- Price: pass 1 — inline script JSON ---
        price: int | None = None
        for script_node in tree.css("script"):
            content = script_node.text()
            if not content or not content.strip():
                continue
            m = _EMBEDDED_PRICE_RE.search(content)
            if m:
                raw = m.group(2).replace(" ", "").rstrip(".,")
                p = _parse_price(raw)
                if p is not None and _MIN_PRICE <= p <= _MAX_PRICE:
                    price = p
                    break

        # --- Price: pass 2 — data-price attribute ---
        if price is None:
            m = _DATA_PRICE_RE.search(html)
            if m:
                p = _parse_price(m.group(1))
                if p is not None and _MIN_PRICE <= p <= _MAX_PRICE:
                    price = p

        if price is None:
            raise FetchError(f"MOYO: no price found on {url!r}")

        # --- Availability ---
        # Patterns sourced from scripts/actions_probe.py (proven on live pages).
        # Matches both "В наявності" and "Є в наявності" (lowercase в).
        # Also checks machine-readable data-is-in-stock attribute as a fallback.
        if re.search(r"[Вв]\s+наявн", html) or re.search(r'data-is-in-stock=["\']1["\']', html):
            in_stock = True
        elif (
            re.search(r"[Вв]ідсутн|[Нн]емає в наявн|[Нн]ет в наличии", html)
            or re.search(r'data-is-in-stock=["\']0["\']', html)
        ):
            in_stock = False
        else:
            print(
                f"[WARN] MOYO: availability text not found on {url}; assuming in_stock=True",
                file=sys.stderr,
            )
            in_stock = True

        # --- Name: <h1> then og:title ---
        name: str | None = None
        h1 = tree.css_first("h1")
        if h1:
            name = h1.text(strip=True) or None
        if not name:
            og = tree.css_first('meta[property="og:title"]')
            if og:
                name = og.attributes.get("content") or None

        return {"price": price, "in_stock": in_stock, "name": name or ""}
