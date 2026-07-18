"""Shared JSON-LD (schema.org/Product) extractor for store pages.

Public interface:
    extract_product(html: str) -> dict | None

Returns {"name": str|None, "price": int|None, "in_stock": bool|None}
or None if no Product schema found in any JSON-LD block.
"""

import json
import re

from selectolax.parser import HTMLParser


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_availability(avail: str | None) -> bool | None:
    """Map a schema.org availability value to bool.

    Accepts both full URL form (https://schema.org/InStock) and bare form (InStock).

    InStock, PreOrder  -> True
    OutOfStock, Discontinued -> False
    Unknown or missing -> None
    """
    if not avail:
        return None
    # Take the last path segment so both URL and bare forms resolve the same way.
    segment = avail.rstrip("/").rsplit("/", 1)[-1].strip()
    if segment in ("InStock", "PreOrder"):
        return True
    if segment in ("OutOfStock", "Discontinued"):
        return False
    return None


_PRICE_CLEANUP_RE = re.compile(r"[^\d.]")


def _parse_price(price_val) -> int | None:
    """Parse a price value to integer UAH.

    Handles int, float, and str (strips spaces and currency symbols).
    Floats are rounded to the nearest integer.
    """
    if price_val is None:
        return None
    if isinstance(price_val, (int, float)):
        return round(price_val)
    s = str(price_val).strip()
    # Remove everything except digits and dot (handles spaces, currency glyphs, commas).
    s = _PRICE_CLEANUP_RE.sub("", s)
    if not s or s == ".":
        return None
    try:
        return round(float(s))
    except ValueError:
        return None


def _find_product(obj) -> dict | None:
    """Recursively search a parsed JSON-LD value for a schema.org/Product node."""
    if isinstance(obj, dict):
        t = obj.get("@type", "")
        types = t if isinstance(t, list) else [t]
        if "Product" in types:
            return obj
        # Descend into @graph arrays.
        for item in obj.get("@graph", []):
            result = _find_product(item)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_product(item)
            if result is not None:
                return result
    return None


def _get_offer(offers) -> dict | None:
    """Return the first offer that has a price field.

    Offers may be a dict (single offer) or a list (multiple offers).
    """
    if isinstance(offers, dict):
        return offers
    if isinstance(offers, list):
        # Prefer the first offer that has an explicit price.
        for offer in offers:
            if isinstance(offer, dict):
                if offer.get("price") is not None or offer.get("Price") is not None:
                    return offer
        # Fallback: return the first offer regardless.
        return offers[0] if offers else None
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_product(html: str) -> dict | None:
    """Extract schema.org/Product data from *html*.

    Parses all <script type="application/ld+json"> blocks via selectolax.
    Malformed JSON blocks are silently skipped.

    Returns {"name": str|None, "price": int|None, "in_stock": bool|None}
    or None if no Product node is found in any block.
    """
    tree = HTMLParser(html)
    scripts = tree.css('script[type="application/ld+json"]')

    product: dict | None = None
    for script in scripts:
        text = script.text()
        if not text or not text.strip():
            continue
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            continue
        product = _find_product(data)
        if product is not None:
            break

    if product is None:
        return None

    # Name
    name = product.get("name") or product.get("Name")
    if isinstance(name, list):
        name = name[0] if name else None

    # Offer
    offers = product.get("offers") or product.get("Offers")
    offer = _get_offer(offers)

    price: int | None = None
    in_stock: bool | None = None

    if offer:
        raw_price = offer.get("price") if offer.get("price") is not None else offer.get("Price")
        price = _parse_price(raw_price)

        avail = offer.get("availability") or offer.get("Availability")
        in_stock = _parse_availability(str(avail) if avail is not None else None)

    return {
        "name": str(name) if name is not None else None,
        "price": price,
        "in_stock": in_stock,
    }
