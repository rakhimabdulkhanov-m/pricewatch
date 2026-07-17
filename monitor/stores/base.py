"""Base class for store adapters."""

from abc import ABC, abstractmethod


class FetchError(Exception):
    """Raised by a StoreAdapter when a product page cannot be fetched or parsed."""


class StoreAdapter(ABC):
    """Abstract base for a store-specific price scraper.

    Each concrete adapter handles one online store.
    """

    @abstractmethod
    def fetch_product(self, url: str) -> dict:
        """Fetch price and stock status for a product at *url*.

        Returns a dict with exactly these keys:
            price    (int)  - price in UAH (integer, no kopecks)
            in_stock (bool) - True if the product is available for purchase
            name     (str)  - product name as it appears on the store page

        Raises FetchError on any network or parsing failure so the
        orchestrator can track consecutive failures without treating a
        single error as an out-of-stock event.
        """
