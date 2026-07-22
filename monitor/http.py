"""Shared HTTP layer for store adapters.

Public interface:
    fetch_page(url: str) -> tuple[str, str]
        Returns (html_text, final_url_as_str). Plain httpx client.
    fetch_page_impersonate(url: str) -> tuple[str, str]
        Same contract, but sends a real Chrome TLS/JA3 handshake via curl_cffi
        so Cloudflare's passive fingerprinting lets the request through
        (used by the Rozetka adapter). See monitor/stores/rozetka.py.

Behaviour (both functions):
  - Sleeps 2-4 s (random jitter) before every request.
  - 3 retries with exponential backoff (2 / 4 / 8 s) on network errors and HTTP 5xx.
  - HTTP 403 / 404 raises FetchError immediately (no retry).
  - Any other non-200 status raises FetchError after retries are exhausted.
"""

import random
import time

import httpx

from monitor.stores.base import FetchError

_HEADERS: dict[str, str] = {
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

_TIMEOUT = 15.0
_RETRY_BACKOFFS = (2, 4, 8)

# Module-level client for connection pooling; created lazily.
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            headers=_HEADERS,
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
    return _client


def fetch_page(url: str) -> tuple[str, str]:
    """Fetch *url* and return *(html_text, final_url)*.

    Sleeps 2-4 s before making the first request (mandatory jitter).
    Retries up to 3 times on transient errors (network + 5xx) with 2/4/8 s backoff.
    HTTP 403/404 -> immediate FetchError, no retry.
    """
    time.sleep(random.uniform(2.0, 4.0))

    client = _get_client()
    last_exc: Exception | None = None

    for attempt in range(4):  # attempt 0 = initial, 1-3 = retries
        if attempt > 0:
            time.sleep(_RETRY_BACKOFFS[attempt - 1])

        try:
            resp = client.get(url)
        except httpx.TimeoutException as exc:
            last_exc = FetchError(f"Timeout fetching {url}: {exc}")
            continue
        except httpx.RequestError as exc:
            last_exc = FetchError(f"Network error fetching {url}: {exc}")
            continue

        status = resp.status_code

        if status in (403, 404):
            raise FetchError(f"HTTP {status} for {url}")

        if status >= 500:
            last_exc = FetchError(f"HTTP {status} for {url}")
            continue

        if status != 200:
            raise FetchError(f"HTTP {status} for {url}")

        return resp.text, str(resp.url)

    raise last_exc or FetchError(f"Failed to fetch {url} after retries")


# ---------------------------------------------------------------------------
# TLS-impersonating fetch (Cloudflare-protected stores)
# ---------------------------------------------------------------------------
#
# A plain httpx request to a Cloudflare-fingerprinting store (e.g. Rozetka)
# returns HTTP 403 "Just a moment..." even with a correct Chrome User-Agent —
# Cloudflare reads the TLS/JA3 handshake, and Python's stack does not look like
# Chrome. curl_cffi replays a real Chrome TLS fingerprint, so the passive check
# passes without a browser. Kept as a SEPARATE function (its own client) so the
# proven httpx path above stays untouched.
#
# NB: this defeats passive fingerprinting only. From a datacenter IP (e.g. CI
# runners) Cloudflare additionally challenges by ASN reputation and still 403s —
# run this from a residential IP or a residential proxy. See BYPASS.md.

# Imported lazily so the package still imports where curl_cffi is absent
# (the httpx stores keep working; only Rozetka needs it).
_cffi_session = None


def _get_cffi_session():
    global _cffi_session
    if _cffi_session is None:
        from curl_cffi import requests as cffi_requests

        _cffi_session = cffi_requests.Session(impersonate="chrome")
    return _cffi_session


def fetch_page_impersonate(url: str) -> tuple[str, str]:
    """Fetch *url* with a Chrome TLS fingerprint; return *(html_text, final_url)*.

    Same jitter / retry / status semantics as :func:`fetch_page`, but routed
    through curl_cffi so Cloudflare's passive TLS fingerprinting is satisfied.
    """
    from curl_cffi import CurlError

    time.sleep(random.uniform(2.0, 4.0))

    session = _get_cffi_session()
    last_exc: Exception | None = None

    for attempt in range(4):  # attempt 0 = initial, 1-3 = retries
        if attempt > 0:
            time.sleep(_RETRY_BACKOFFS[attempt - 1])

        try:
            resp = session.get(url, timeout=_TIMEOUT, allow_redirects=True)
        except CurlError as exc:
            last_exc = FetchError(f"Network error fetching {url}: {exc}")
            continue

        status = resp.status_code

        if status in (403, 404):
            raise FetchError(f"HTTP {status} for {url}")

        if status >= 500:
            last_exc = FetchError(f"HTTP {status} for {url}")
            continue

        if status != 200:
            raise FetchError(f"HTTP {status} for {url}")

        return resp.text, str(resp.url)

    raise last_exc or FetchError(f"Failed to fetch {url} after retries")
