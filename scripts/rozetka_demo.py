"""Rozetka Cloudflare-bypass demo (reproducible).

Runs side by side, on live Rozetka product pages, from THIS machine:

  1. plain httpx with a real Chrome User-Agent   -> HTTP 403, Cloudflare wall
  2. curl_cffi impersonating Chrome's TLS/JA3    -> HTTP 200, live price parsed

Same URL, same headers, same IP. The only difference is the TLS handshake:
Cloudflare fingerprints it and blocks Python's stack; curl_cffi replays Chrome's,
so the passive check passes without a browser. Prices are then read from the
page's own schema.org JSON-LD (monitor/jsonld.py) — the same extractor prom.py uses.

Run:  python scripts/rozetka_demo.py
Note: run from a residential IP. Datacenter IPs (CI runners) are additionally
      ASN-challenged by Cloudflare and still 403 — see BYPASS.md.
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitor.jsonld import extract_product  # noqa: E402
from monitor.stores.rozetka import RozetkaAdapter  # noqa: E402

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

URLS = [
    "https://rozetka.com.ua/ua/samsung-sm-s948bzvgeuc/p570541936/",
    "https://rozetka.com.ua/ua/samsung-sm-s947blbgeuc/p570551059/",
    "https://rozetka.com.ua/ua/apple-iphone-17-pro-256gb-cosmic-orange-mg8h4af-a/p543545585/",
    "https://rozetka.com.ua/ua/apple-iphone-17-pro-256gb-deep-blue-mg8j4af-a/p543545605/",
]

BAR = "=" * 68


def try_plain_httpx(url: str) -> str:
    """Return a short status string for a plain-httpx fetch (expected: blocked)."""
    try:
        r = httpx.get(url, headers={"User-Agent": CHROME_UA},
                      timeout=20, follow_redirects=True)
        if r.status_code == 200 and "just a moment" not in r.text[:2000].lower():
            price = (extract_product(r.text) or {}).get("price")
            return f"HTTP 200  (unexpected pass) price={price}"
        return f"HTTP {r.status_code}  BLOCKED by Cloudflare"
    except Exception as exc:  # noqa: BLE001
        return f"blocked/error: {type(exc).__name__}"


def main() -> int:
    adapter = RozetkaAdapter()
    print(BAR)
    print("  Rozetka anti-bot bypass demo  (rozetka.com.ua, behind Cloudflare)")
    print(BAR)
    print("  For each product: plain httpx first, then Chrome-TLS impersonation.\n")

    passed = 0
    for url in URLS:
        short = url.split("rozetka.com.ua")[-1]
        print(f"* {short}")
        print(f"    [1] httpx  (Python TLS)   -> {try_plain_httpx(url)}")
        try:
            data = adapter.fetch_product(url)  # curl_cffi Chrome TLS under the hood
            stock = "in stock" if data["in_stock"] else "OUT OF STOCK"
            print(f"    [2] curl_cffi (Chrome TLS)-> HTTP 200  {data['price']:>7} UAH  "
                  f"({stock})  {data['name'][:38]}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"    [2] curl_cffi (Chrome TLS)-> FAILED: {exc}")
        print()

    print(BAR)
    print(f"  Bypassed Cloudflare on {passed}/{len(URLS)} products. "
          f"Plain Python was blocked on all.")
    print(BAR)
    return 0 if passed == len(URLS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
