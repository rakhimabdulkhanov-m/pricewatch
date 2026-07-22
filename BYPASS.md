# Bypassing Cloudflare on Rozetka (anti-bot scraping)

Rozetka (rozetka.com.ua) is Ukraine's largest electronics marketplace and sits
behind Cloudflare. A normal scraper gets HTTP 403 "Just a moment..." on every
request — including `robots.txt`. This note documents how PriceWatch reads live
Rozetka prices anyway, for public product data, and — just as important — where
the honest limits are.

## Reproduce it in 20 seconds

```
pip install -r requirements.txt
python scripts/rozetka_demo.py
```

On each live product it runs plain `httpx` first, then the adapter. Same URL,
same headers, same IP — plain Python is blocked, the adapter passes:

```
* /ua/samsung-sm-s948bzvgeuc/p570541936/
    [1] httpx  (Python TLS)   -> HTTP 403  BLOCKED by Cloudflare
    [2] curl_cffi (Chrome TLS)-> HTTP 200    65299 UAH  (in stock)  Samsung Galaxy S26 Ultra
```

## Cloudflare defends this in two independent layers

**Layer 1 — passive TLS/JA3 fingerprinting.** Before any HTML is served,
Cloudflare inspects the TLS handshake. Python's `httpx`/`requests` produce a TLS
ClientHello that does not look like a browser's, so the request is fingerprinted
as a bot and 403'd — *even with a perfect `User-Agent: Chrome` header*. The UA
string is not the tell; the handshake is.

The fix is not a headless browser. [`curl_cffi`](https://github.com/lexiforest/curl_cffi)
is libcurl built against BoringSSL and **replays a real Chrome TLS/JA3
fingerprint** (`impersonate="chrome"`). The handshake now matches Chrome, the
passive check passes, and the normal server HTML comes back — no JavaScript
engine, no Turnstile solving, milliseconds not seconds. This works here
specifically because Rozetka runs *passive* fingerprinting, not an interactive
JS/Turnstile challenge; there is nothing to "solve," only a fingerprint to match.

Extraction after that is trivial: Rozetka embeds `schema.org/Product` JSON-LD in
the page, so price/stock/name come straight out of `monitor/jsonld.py` — the same
extractor prom.py uses. The demoed skill is the **access**, not the parse.

**Layer 2 — IP-reputation by ASN.** Passing the TLS check is necessary but not
sufficient. Cloudflare *also* scores the source IP's autonomous system. Requests
from residential/mobile ASNs pass; requests from datacenter ASNs
(AWS, Azure, GCP — and therefore GitHub Actions runners) get an extra
Managed Challenge and 403 regardless of a perfect TLS fingerprint.

This is measured, not assumed. The exact same code that returns HTTP 200 from a
home connection returns HTTP 403 from a GitHub Actions runner (Azure):

```
[403] CF_CHALLENGE  https://rozetka.com.ua/ua/samsung-sm-s948bzvgeuc/p570541936/
ROZETKA DATACENTER VERDICT: FAIL (0/3 with price)   # from an Actions runner
```

## Consequence for PriceWatch

- moyo and prom are **not** Cloudflare-fingerprinted, so they run in the free
  GitHub Actions cron as before. Rozetka is **not wired into the cron** — from a
  datacenter IP it can only fail, and a monitor full of failing rows looks broken.
- The Rozetka adapter (`monitor/stores/rozetka.py`) is production-shaped and
  isolated: the orchestrator catches its errors per (product, store) pair, so
  Rozetka can never destabilise the live moyo/prom monitoring.
- To run Rozetka **live** you need a residential/mobile egress. Two honest ways:
  - out of band from a residential machine, against its own state file (no
    collision with the cron):
    ```
    python -m monitor.run --config config/products.rozetka.yaml --state state/rozetka.json
    ```
  - in production, a residential/mobile proxy — the standard, cheap
    (product-data scraping is a few MB) way commercial scrapers handle this.
    That is a paid dependency and deliberately not baked into this free demo.

## Legality / scope

Public product data only (price, availability, name) — the same data Rozetka
publishes to Google via JSON-LD. No login, no paywall, no personal data, polite
2–4 s jitter between requests. This is anti-bot *bypass* for public data, not
account or access-control bypass.
