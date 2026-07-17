"""Weekly summary report builder.

Filled in during T8.

Planned public interface:

    build_report(history: list[dict]) -> str

        Accepts a list of historical price/stock rows (as read from Google
        Sheets or a local CSV) and returns a Markdown-formatted weekly
        summary string ready for posting to Telegram.

        Summary includes: lowest price seen this week per product,
        number of stock-out events, stores with the most price changes.

Works alongside chartstyle.py which supplies the matplotlib styling.
"""
