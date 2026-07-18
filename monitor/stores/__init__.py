"""Store adapter registry.

Usage:
    from monitor.stores import get_adapter

    adapter = get_adapter("moyo")   # returns MoyoAdapter instance or None
"""

from monitor.stores.base import FetchError, StoreAdapter
from monitor.stores.moyo import MoyoAdapter
from monitor.stores.prom import PromAdapter
from monitor.stores.stub import StubAdapter

_ADAPTERS: dict[str, StoreAdapter] = {
    "stub": StubAdapter(),
    "moyo": MoyoAdapter(),
    "prom": PromAdapter(),
}


def get_adapter(store_id: str) -> StoreAdapter | None:
    """Return the registered adapter for *store_id*, or None if unknown."""
    return _ADAPTERS.get(store_id)


__all__ = ["FetchError", "StoreAdapter", "get_adapter"]
