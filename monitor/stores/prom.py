"""Store adapter for Prom.ua.

Prom product pages embed schema.org/Product data in JSON-LD (confirmed
locally 2026-07-17, 3/3 URLs, probe method: json-ld).

Extraction is fully delegated to monitor.jsonld.extract_product.
If the page has no JSON-LD Product or the product has no price, FetchError
is raised so the orchestrator records a fetch-failure (not an out-of-stock).
"""

from monitor.http import fetch_page
from monitor.jsonld import extract_product
from monitor.stores.base import FetchError, StoreAdapter


class PromAdapter(StoreAdapter):
    """Fetches price and availability from prom.ua product pages via JSON-LD."""

    def fetch_product(self, url: str) -> dict:
        html, _final_url = fetch_page(url)

        product = extract_product(html)

        if product is None:
            raise FetchError(f"Prom: no JSON-LD Product schema found on {url!r}")

        if product["price"] is None:
            raise FetchError(f"Prom: JSON-LD Product has no price on {url!r}")

        # If availability is absent from the schema, treat as in stock
        # (Prom omits availability on some pages for in-stock items).
        in_stock = product["in_stock"]
        if in_stock is None:
            in_stock = True

        return {
            "price": product["price"],
            "in_stock": in_stock,
            "name": product["name"] or "",
        }
