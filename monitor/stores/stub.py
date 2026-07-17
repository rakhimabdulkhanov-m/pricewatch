"""Stub store adapter — returns fixed data, used for --dry-run testing."""

from monitor.stores.base import StoreAdapter

# Fixed data keyed by URL so different products can return distinct prices.
_STUB_DATA: dict[str, dict] = {
    "https://example.com/iphone-15-128": {
        "price": 32999,
        "in_stock": True,
        "name": "Apple iPhone 15 128GB (stub)",
    },
}

_DEFAULT = {
    "price": 9999,
    "in_stock": True,
    "name": "Stub product",
}


class StubAdapter(StoreAdapter):
    """Returns pre-set data without making any network requests."""

    def fetch_product(self, url: str) -> dict:
        return dict(_STUB_DATA.get(url, _DEFAULT))
