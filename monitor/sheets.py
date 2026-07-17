"""Google Sheets history writer.

Filled in during T5.

Planned public interface:

    append_rows(spreadsheet_id: str, rows: list[dict], credentials_json: str) -> None

        Appends one row per (product, store) result to a Google Sheet tab
        named after the current month (e.g. "2026-07").
        Each row: [timestamp, product_id, store_id, name, price, in_stock].

        credentials_json is the path to a service-account JSON key file
        (never committed; passed via environment variable GOOGLE_CREDENTIALS).

Requires: google-auth, google-api-python-client (not yet in requirements.txt;
added in T5).
"""
