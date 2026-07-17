"""Matplotlib style sheet for PriceWatch charts.

Filled in during T8.

Planned public interface:

    apply_style() -> None

        Applies a consistent visual style to all subsequent matplotlib
        figures: dark background, sans-serif font, UAH-formatted y-axis,
        one warm accent color (#E8A87C) for the price line.

    price_chart(history: list[dict], product_id: str, output_path: str) -> None

        Renders a price-over-time line chart for *product_id* and saves
        it as a PNG to *output_path*.  Each store is a separate line.
        Called by report.py; output PNGs are attached to the Telegram
        weekly summary.

Requires: matplotlib (already in requirements.txt).
"""
