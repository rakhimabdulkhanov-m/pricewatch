"""
GitHub Actions IP blocking probe for Ukrainian electronics stores.
Tests whether MOYO (control, confirmed PASS) and prom.ua are reachable
from datacenter IPs.

Usage: python scripts/actions_probe.py
PASS criterion: >=2 of 3 URLs per store return HTTP 200 with a price extracted.
"""

import json
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

REQUEST_DELAY = 3   # seconds between requests (mandatory)
TIMEOUT = 20        # seconds per request

# 3 URLs per store; all confirmed 200 locally on 2026-07-17.
# moyo: known-good control (PASS on Actions in prior runs).
# prom: locally PASS 2026-07-17 — prices via JSON-LD; nginx (no Cloudflare); to be confirmed from datacenter IPs.
# rozetka: excluded — Cloudflare browser challenge (cf-mitigated: challenge, HTTP 403) even from local residential IPs.
STORE_URLS: dict[str, list[str]] = {
    "moyo": [
        "https://www.moyo.ua/ua/smartfon_samsung_galaxy_s25_ultra_12_256gb_titanium_whitesilver_sm-s938bzsdeuc_/628561.html",
        "https://www.moyo.ua/ua/smartfon_samsung_galaxy_s25_12_256gb_navy_sm-s931bdbgeuc_/628576.html",
        "https://www.moyo.ua/ua/smartfon_samsung_galaxy_a07_4_128gb_black_sm-a075fzkgsek_/658675.html",
    ],
    # prom.ua: marketplace product pages; prices in JSON-LD offers.price (confirmed locally 2026-07-17).
    # URL format: /ua/m-[merchant-id]-[slug].html (NOT /ua/p[id] which is a dead pattern).
    "prom": [
        "https://prom.ua/ua/m-8667243275922823703-smartfon-samsung-galaxy.html",
        "https://prom.ua/ua/m5162719999084429834-smartfon-samsung-galaxy.html",
        "https://prom.ua/ua/m6871442186131025987-smartfon-samsung-galaxy.html",
    ],
}


@dataclass
class Result:
    store: str
    url: str
    status: Optional[int] = None
    price: Optional[str] = None       # extracted value or None
    availability: Optional[str] = None
    method: str = "none"
    error: Optional[str] = None
    antibot: bool = False
    antibot_notes: str = ""


# ---------------------------------------------------------------------------
# Extraction helpers (self-contained, no monitor/ imports)
# ---------------------------------------------------------------------------

def detect_antibot(status: int, text: str) -> tuple[bool, str]:
    notes = []
    if status in (403, 503):
        notes.append(f"HTTP {status}")
    low = text.lower()
    if "cloudflare" in low and ("checking your browser" in low or "ray id" in low):
        notes.append("Cloudflare challenge")
    if "pardon our interruption" in low:
        notes.append("Imperva/Incapsula WAF")
    if "incapsula" in low or "imperva" in low:
        notes.append("Imperva WAF header")
    if "captcha" in low:
        notes.append("captcha")
    if "access denied" in low:
        notes.append("access denied")
    if status == 200 and len(text) < 15_000 and "noscript" in low and not notes:
        notes.append(f"suspected JS challenge ({len(text)} bytes)")
    return bool(notes), "; ".join(notes)


def extract_json_ld_blocks(html: str) -> list[dict]:
    results = []
    pat = re.compile(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for m in pat.finditer(html):
        try:
            results.append(json.loads(m.group(1).strip()))
        except json.JSONDecodeError:
            pass
    return results


def find_product_schema(blocks: list[dict]) -> Optional[dict]:
    def check(obj):
        if isinstance(obj, dict):
            t = obj.get("@type", "")
            types = t if isinstance(t, list) else [t]
            if "Product" in types:
                return obj
            for item in obj.get("@graph", []):
                r = check(item)
                if r:
                    return r
        elif isinstance(obj, list):
            for item in obj:
                r = check(item)
                if r:
                    return r
        return None

    for block in blocks:
        r = check(block)
        if r:
            return r
    return None


def price_from_json_ld(html: str) -> tuple[Optional[str], Optional[str]]:
    blocks = extract_json_ld_blocks(html)
    product = find_product_schema(blocks)
    if not product:
        return None, None
    offers = product.get("offers") or product.get("Offers")
    if not offers:
        return None, None
    offer = offers[0] if isinstance(offers, list) else offers
    price = offer.get("price") or offer.get("Price")
    avail = offer.get("availability") or offer.get("Availability")
    return (str(price) if price is not None else None), (str(avail) if avail else None)


def price_from_embedded_json(html: str) -> Optional[str]:
    pat = re.compile(
        r'"(?:price|Price|currentPrice|salePrice|regularPrice)"\s*:\s*(["\']?)(\d[\d.,]*)\1',
        re.IGNORECASE,
    )
    script_pat = re.compile(r'<script[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
    for sm in script_pat.finditer(html):
        content = sm.group(1)
        if not content.strip():
            continue
        m = pat.search(content)
        if m:
            raw = m.group(2).replace(" ", "").rstrip(".,")
            try:
                val = float(raw.replace(",", "."))
                if 100 <= val <= 1_000_000:
                    return raw
            except ValueError:
                pass
    return None


def price_from_data_attr(html: str) -> Optional[str]:
    pat = re.compile(r'data-price=["\']([0-9]+(?:\.[0-9]+)?)["\']', re.IGNORECASE)
    for m in pat.finditer(html):
        try:
            val = float(m.group(1))
            if 100 <= val <= 1_000_000:
                return str(int(val)) if val == int(val) else m.group(1)
        except ValueError:
            pass
    return None


def availability_from_html(html: str) -> Optional[str]:
    if re.search(r'class="[^"]*out-of-stock[^"]*"', html, re.IGNORECASE):
        return "OutOfStock"
    if re.search(r'class="[^"]*in-stock[^"]*"', html, re.IGNORECASE):
        return "InStock"
    if re.search(r'[Вв]\s+наявн', html):
        return "InStock"
    if re.search(r'[Вв]ідсутн|[Нн]емає в наявн|[Нн]ет в наличии', html):
        return "OutOfStock"
    return None


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------

def probe_url(client: httpx.Client, store: str, url: str) -> Result:
    r = Result(store=store, url=url)
    try:
        resp = client.get(url, timeout=TIMEOUT, follow_redirects=True)
        r.status = resp.status_code
        text = resp.text
        r.antibot, r.antibot_notes = detect_antibot(resp.status_code, text)

        if resp.status_code != 200:
            return r

        # Try JSON-LD first (Allo), then embedded JSON (Foxtrot TV, Moyo), then data-attr (Foxtrot)
        p, av = price_from_json_ld(text)
        if p is not None:
            r.price = p
            r.availability = av
            r.method = "json-ld"
        else:
            ep = price_from_embedded_json(text)
            if ep:
                r.price = ep
                r.method = "embedded-json"
            else:
                dp = price_from_data_attr(text)
                if dp:
                    r.price = dp
                    r.method = "html-data-attr"

        if not r.availability:
            r.availability = availability_from_html(text)

    except httpx.TimeoutException:
        r.error = "timeout"
    except httpx.RequestError as exc:
        r.error = f"request_error: {exc}"
    except Exception as exc:
        r.error = f"unexpected: {exc}"
    return r


def main():
    all_results: dict[str, list[Result]] = {}
    first = True

    with httpx.Client(headers=HEADERS) as client:
        for store, urls in STORE_URLS.items():
            store_results = []
            for url in urls:
                if not first:
                    print(f"  [delay {REQUEST_DELAY}s]", flush=True)
                    time.sleep(REQUEST_DELAY)
                first = False
                print(f"  fetching {store}: {url}", flush=True)
                r = probe_url(client, store, url)
                store_results.append(r)
            all_results[store] = store_results

    # Per-store report
    for store, results in all_results.items():
        passing = sum(
            1 for r in results
            if r.status == 200 and r.price is not None
        )
        verdict = "PASS" if passing >= 2 else "FAIL"
        print(f"\n{'='*60}")
        print(f"STORE: {store.upper()}  |  VERDICT: {verdict}  ({passing}/{len(results)} with price)")
        print(f"{'='*60}")
        for r in results:
            short = r.url if len(r.url) <= 80 else r.url[:77] + "..."
            status_s = str(r.status) if r.status else f"ERR({r.error})"
            price_s = r.price if r.price is not None else "NONE"
            avail_s = r.availability or "-"
            antibot_s = f" [ANTIBOT: {r.antibot_notes}]" if r.antibot else ""
            print(f"  [{status_s}] {short}")
            print(f"         price={price_s}  avail={avail_s}  method={r.method}{antibot_s}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    overall_pass = True
    for store, results in all_results.items():
        passing = sum(1 for r in results if r.status == 200 and r.price is not None)
        verdict = "PASS" if passing >= 2 else "FAIL"
        if verdict == "FAIL":
            overall_pass = False
        methods = {r.method for r in results if r.method != "none"}
        print(f"  {store:<10} {verdict}  ({passing}/{len(results)} URLs with price)  methods={methods or {'none'}}")
    print(f"\n  OVERALL: {'ALL PASS' if overall_pass else 'SOME STORES FAIL - datacenter IP blocking detected'}")


if __name__ == "__main__":
    main()
