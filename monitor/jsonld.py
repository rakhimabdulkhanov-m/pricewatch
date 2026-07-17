"""JSON-LD structured-data extractor for store pages.

Filled in during T3 (store feasibility gate).

Planned public interface:

    extract_jsonld_price(html: str) -> dict | None

        Parses <script type="application/ld+json"> blocks in *html* and
        returns a dict with keys {price, currency, availability} if a
        Product or Offer schema is found, or None if absent.

This module is intentionally empty until T3 confirms which stores expose
JSON-LD and which require CSS-selector fallbacks.
"""
