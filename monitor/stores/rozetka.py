"""Store adapter for Rozetka (rozetka.com.ua) — a Cloudflare-protected store.

Rozetka sits behind Cloudflare, which fingerprints the TLS/JA3 handshake: a
plain httpx request returns HTTP 403 "Just a moment..." even with a correct
Chrome User-Agent. This adapter fetches through
:func:`monitor.http.fetch_page_impersonate`, which replays a real Chrome TLS
fingerprint via curl_cffi and passes the passive check without a browser.

Extraction is the *easy* half here: Rozetka product pages embed
schema.org/Product in JSON-LD, so price/availability/name come straight from
:func:`monitor.jsonld.extract_product` — the same path as prom.py. The demoed
skill is the *access* (getting past Cloudflare), not the parse.

See BYPASS.md for the full anti-bot writeup and the datacenter-IP caveat.
"""

import re

from monitor.http import fetch_page_impersonate
from monitor.jsonld import extract_product
from monitor.stores.base import FetchError, StoreAdapter

# Rozetka product pages are .../p<digits>/. A redirect to a category/search
# page (no /p<id>/) means the product is gone — mirror moyo's URL guard.
_PRODUCT_URL_RE = re.compile(r"/p\d+/?(?:[?#].*)?$")


class RozetkaAdapter(StoreAdapter):
    """Fetches price and availability from rozetka.com.ua via TLS impersonation."""

    def fetch_product(self, url: str) -> dict:
        html, final_url = fetch_page_impersonate(url)

        # Guard: a redirect away from a /p<id>/ URL means the product is gone.
        if not _PRODUCT_URL_RE.search(final_url):
            raise FetchError(
                f"Rozetka: redirected to non-product URL {final_url!r} (original: {url!r})"
            )

        product = extract_product(html)

        if product is None:
            raise FetchError(f"Rozetka: no JSON-LD Product schema found on {url!r}")

        if product["price"] is None:
            raise FetchError(f"Rozetka: JSON-LD Product has no price on {url!r}")

        # Availability absent from the schema -> treat as in stock (same as prom).
        in_stock = product["in_stock"]
        if in_stock is None:
            in_stock = True

        return {
            "price": product["price"],
            "in_stock": in_stock,
            "name": product["name"] or "",
        }
