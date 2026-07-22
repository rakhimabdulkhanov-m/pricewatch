# HANDOFF — Case 3 "PriceWatch" (written 2026-07-18, after launch)

Read this file at the start of the next session. It is the full state; no other prompt needed.
User kickoff: just say "read HANDOFF.md in case3-pricewatch and continue" (or paste this file).

## What this is

Portfolio case #3: price-monitoring bot for Ukrainian electronics stores (MOYO + Prom).
Scrapes prices every 3 h in GitHub Actions, history in Google Sheets, Telegram channel
notifications on price/stock changes, weekly styled chart every Sunday.
Purpose: portfolio artifact for the "automation/integrations/scraping" profile label.
NOT published to Freelancehunt yet — that is Session B's job (see below).

## Status at handoff: LAUNCHED, accumulating history

- Repo: https://github.com/rakhimabdulkhanov-m/pricewatch (public), local: G:\claude\freelance\case3-pricewatch
- Seed run succeeded 2026-07-18 09:16 UTC. "PriceWatch is live" message confirmed in channel.
- Cron: monitor every 3 h (`17 */3 * * *`), weekly report Sunday 06:17 UTC (`weekly.yml`).
- Channel: https://t.me/pricewatch_demo (posts in English, prices in ₴ — decision AD-10).
- Sheets: history + current tabs via Apps Script webhook (apps-script/Code.gs, DEPLOY.md).
  User deleted all test/stub rows 18.07 — sheet is clean, only real data.
- Secrets in GitHub: TG_BOT_TOKEN, SHEETS_WEBHOOK_URL (secrets), TG_CHANNEL_ID (variable).
  Local .env mirrors them (gitignored).
- Tests: 178 passing (`python -m pytest -q`).
- 3-day history window: 18.07 09:16 UTC → ready from ~Tue 21.07. First weekly chart
  auto-posts Sunday 20.07 ~09:17 Kyiv (will have only ~2 days of data — acceptable,
  report degrades gracefully; the GOOD chart for portfolio comes later).

## Products

config/products.yaml: 15 products, 25 product-store pairs, 10 products on both stores.
Seed message said "14 products" because macbook-air-m2-256 (prom-only) had one transient
fetch failure on the seed run — it will appear once a later run fetches it. Failure
tracking: warns in channel only after 2 consecutive failures per pair.

## Architecture (1-line map)

monitor/run.py orchestrator → stores/moyo.py + stores/prom.py adapters (http.py shared
client, jsonld.py extractor) → state/latest.json diff (state.py) → notify.py (Telegram
HTML) + sheets.py (webhook) → report.py + chartstyle.py (Sumi-e matplotlib, Literata +
JetBrains Mono, en/uk locales, percent-change axis). Workflows commit state back
(monitor.yml has the critical `if: always() && steps.install.outcome == 'success'`).

## Decisions already made (do NOT relitigate)

- Stores in the CRON: MOYO + Prom only (no Cloudflare). Comfy/Foxtrot/Allo left out.
- Rozetka (Cloudflare) ADDED 2026-07-22 as an adapter, NOT wired into the cron.
  The earlier "anti-bot bypass decided against" is superseded — but the reasoning
  was half right: bypass works, the CRON just can't use it. Specifics (do not relitigate):
  - Cloudflare here is PASSIVE TLS/JA3 fingerprinting, not an interactive challenge.
    curl_cffi impersonate="chrome" passes it from a residential IP -> HTTP 200 + live
    price via the existing jsonld.py. Proven. No browser/Turnstile-solving involved.
  - Datacenter IPs (GitHub Actions/Azure) are ALSO ASN-challenged -> 403 even with
    the right TLS. MEASURED on an Actions runner (0/3). So Rozetka is deliberately
    kept out of the cron; from a datacenter IP it can only fail.
  - Delivery = reproducible demo + writeup, not a live cron store. See BYPASS.md.
    New code: monitor/stores/rozetka.py, http.fetch_page_impersonate, scripts/rozetka_demo.py,
    config/products.rozetka.yaml (optional residential run, own state file),
    tests/test_rozetka.py. run.py gained --config/--state. requirements += curl_cffi.
  - Live Rozetka is possible only from a residential IP/proxy (paid, not in the free
    demo): python -m monitor.run --config config/products.rozetka.yaml --state state/rozetka.json
  - Client-facing VISUAL done: before/after card (403 wall vs live prices), warm-editorial
    Sumi-e, EN + UK. scripts/render_bypass_card.py -> rozetka_bypass_en.png +
    publish-assets/rozetka_bypass_uk.png (2000x2000). Data = live demo 2026-07-22.
    Optional follow-up: an animated GIF of rozetka_demo.py for worldwide platforms
    (needs a terminal recorder; static card covers the FH one-image card already).
- AD-10 language: channel EN, prices ₴; FH card cover assets UK + EN (worldwide market).
- English-first naming everywhere (IDs, bot pricewatchdemo_bot, repo, tabs).
- Chart style: warm editorial "Sumi-e" (paper #F4F1EA, ink, accent #B23A2C) — anti-default
  vs commoditized dark-techno AI look (field-measured 12.07).
- 15 products is enough: the case sells the MECHANISM (adding a product = 3 lines of yaml);
  scale is a config knob, not a capability.

## Session B — status 22.07.2026

DONE:
- Runs verified: monitor.yml green every ~3h across 20–22.07; weekly.yml posted once
  Sun 19.07 (only ~1.5 days data then). Real state = 15 products / 25 pairs, live
  moyo+prom prices, some genuinely out-of-stock. Data is real and honest.
- Case text drafted: fh-case.md (uk/ru/en), buyer-psychology-first, honest-data +
  live-channel-first voice (mirrors case1/case2), Rozetka bypass woven in + linked.
- Bypass fully shipped (see the decisions block above).

HELD / NEXT — resume ~Sun 26.07 (user decision 22.07: wait for a full 7-day chart
so the hero has real movement; 4 days is too flat):
1. Weekly chart: confirm weekly.yml posted a full 7-day chart Sun 26.07 (or
   workflow_dispatch it once ≥7 days of history since the 18.07 seed exist, i.e. ≥25.07).
   NOTE: the repo's pricewatch_weekly_en.png is STALE STUB data (Samsung TV/Dyson,
   pre-seed dates) — do NOT ship it; render from real Sheet history.
2. Groom: pick the week window with the most visible movement; confirm the channel
   has a few clean real alerts (not just the seed msg); set Sheet share = anyone-with-
   link-can-view and fill [SHEET_VIEW_URL] in fh-case.md (public sheet URL not yet
   recorded anywhere — get it from the live spreadsheet).
3. Cover (FH one image = the APP, NOT the bypass card): hero = the real weekly chart
   + title + one-line payoff. uk + en, 2160×2160, cover HTML → headless Chrome, reuse
   chartstyle. Design it AROUND the real chart on 26.07 (not before — avoids rework).
4. Publish FH card (cover-uk, category per bid), paste fh-case.md Title/Description (uk).
   Update profile. Add en set + bypass card (publish-assets/rozetka_bypass_*.png) to
   Upwork/PPH when those go live.

Kickoff for the 26.07 session: "read HANDOFF.md in case3-pricewatch — finish + publish
case3 per the HELD/NEXT list (full-week chart is now available)."

## Post-launch chores (low priority)

- Swap classic GitHub token (in local git remote URL) for fine-grained repo-scoped token.
- Sheets has no delete API (doPost appends only) — cleanup is manual in the spreadsheet.
- Scratchpad helper scripts dispatch.py / pollrun.py exist in session temp (regenerate
  if needed: plain GitHub API workflow_dispatch with token parsed from git remote URL).
