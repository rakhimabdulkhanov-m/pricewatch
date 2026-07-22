"""GitHub Actions datacenter-IP probe for Rozetka (Cloudflare-protected).

Question this answers: does curl_cffi Chrome-TLS impersonation pass Rozetka's
Cloudflare from an Azure/GitHub-Actions datacenter IP, or does Cloudflare
Managed-Challenge the datacenter ASN regardless of TLS fingerprint?

Locally (residential UA IP): plain httpx -> HTTP 403 CF challenge;
curl_cffi impersonate=chrome -> HTTP 200, price parsed from JSON-LD.
This script re-runs the curl_cffi path from the runner and reports.

PASS: >=2 of 3 product URLs return 200 with a price extracted.
"""

import re
import sys
import time

from curl_cffi import requests

URLS = [
    "https://rozetka.com.ua/ua/samsung-sm-s948bzvgeuc/p570541936/",
    "https://rozetka.com.ua/ua/samsung-sm-s948bzkgeuc/p570540502/",
    "https://rozetka.com.ua/ua/samsung-sm-s947blbgeuc/p570551059/",
]

# Minimal inline JSON-LD price extract (no monitor/ import needed in probe).
_LD = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def price_from_html(html: str):
    import json
    for m in _LD.finditer(html):
        try:
            d = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        t = d.get("@type", "")
        if "Product" in (t if isinstance(t, list) else [t]):
            offers = d.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            return offers.get("price"), offers.get("availability")
    return None, None


def main():
    s = requests.Session(impersonate="chrome")
    passing = 0
    for i, u in enumerate(URLS):
        if i:
            time.sleep(3)
        try:
            r = s.get(u, timeout=25)
            body = r.text
            challenged = "just a moment" in body[:2000].lower() or "cf-mitigated" in body.lower()
            price, avail = price_from_html(body)
            tag = "CF_CHALLENGE" if challenged else ("OK" if price else "NO_PRICE")
            print(f"[{r.status_code}] {tag} price={price} avail={avail} len={len(body)}  {u}", flush=True)
            if r.status_code == 200 and price is not None and not challenged:
                passing += 1
        except Exception as exc:
            print(f"[ERR] {type(exc).__name__}: {str(exc)[:160]}  {u}", flush=True)

    verdict = "PASS" if passing >= 2 else "FAIL"
    print(f"\nROZETKA DATACENTER VERDICT: {verdict}  ({passing}/{len(URLS)} with price)")
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
