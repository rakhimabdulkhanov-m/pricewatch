# FH portfolio card — Case 3 (PriceWatch)

Status 22.07.2026: DRAFT. Publish held to ~Sun 26.07, when the weekly.yml chart
covers a full 7-day window with real movement (seed was 18.07; 4 days is too flat
for the hero). Text below is ready for review now; cover renders once the real
chart exists.

Live proof (the clickable things a 0-review profile leans on):
- Telegram channel (real alerts + weekly chart): https://t.me/pricewatch_demo
- Public Google Sheet (full check history): [SHEET_VIEW_URL — fill at publish; set share = anyone with link can VIEW]
- Cloudflare bypass writeup (public repo): https://github.com/rakhimabdulkhanov-m/pricewatch/blob/main/BYPASS.md

FH portfolio card takes exactly ONE image (measured case2) — no gallery. Upload the
2160×2160 cover (the app, NOT the bypass before/after card). The bypass card
(publish-assets/rozetka_bypass_uk.png / _en.png) is a gallery asset for Upwork/PPH
and is linked from the description above — so the bypass is claimable without being
the FH thumbnail.

Suggested FH category: «Веб-скрапінг / парсинг» or «Боти / автоматизація» (pick per the
bid you attach it to). Price via /bid two-step (own floor first, field for positioning).

## Buyer psychology this text is built on

Case-3 client lands here from a bid on price-monitoring / competitor-price tracking /
"notify me when the price or stock changes" / scraping / repricing / automation,
vetting a stranger with 0 reviews. Three questions in their head: (1) will it watch
prices reliably without me babysitting it, (2) does it actually ping me the MOMENT
something changes (not a daily digest I'll ignore), (3) is it real and what does it
cost to keep running. So the order: live Telegram channel first (real alerts, the
only proof a zero-review profile has), real multi-store numbers, "runs itself, 0₴/mo"
(kills the hidden-hosting-fee fear), honest data (shows out-of-stock openly, no faked
movement), then the transfer ("your products, your stores, your competitors, your
alert rules"), and the Cloudflare bypass as the line that separates a real scraper
from a toy. Two skills sold at once: reliable unattended automation AND anti-bot
scraping depth — so the card works for a monitoring bid and a scraping bid.

## Title (uk)

PriceWatch: стежить за цінами в кількох магазинах і пінгує в Telegram, щойно ціна впала

## Description (uk)

Бот стежить за цінами й наявністю товарів у кількох магазинах одночасно і надсилає
сповіщення в Telegram тієї ж хвилини, коли ціна змінилась або товар зник з полиці.
Нічого не треба відкривати й перевіряти руками, він працює сам.

Живий канал зі сповіщеннями: https://t.me/pricewatch_demo
Це не макет. Туди в реальному часі падають зміни цін і наявності по 15 товарах,
а щонеділі — зведений графік цін за тиждень.

Цифри:
- 15 товарів, 25 пар «товар-магазин», два магазини (MOYO і Prom) в одному потоці
- перевірка кожні 3 години, автоматично
- 0 грн/міс на утримання (GitHub Actions, безкоштовний тариф)
- сповіщення в Telegram за секунду після зміни ціни або наявності
- вся історія перевірок лягає в Google Таблицю, щотижня — стильний графік

Дані чесні: якщо товару немає в наявності, я це показую, а не малюю красиву ціну.
Ось та сама історія, відкрита на перегляд: [SHEET_VIEW_URL]

Читаю навіть магазини за захистом Cloudflare. Rozetka блокує звичайний скрапер
(HTTP 403), тож я підробляю TLS-відбиток браузера Chrome і забираю публічні ціни
без жодного браузера, за мілісекунди. Як це влаштовано, з доказом до і після:
https://github.com/rakhimabdulkhanov-m/pricewatch/blob/main/BYPASS.md

Під вас налаштовується так само: ваші товари, ваші магазини, ціни конкурентів.
Правила сповіщень свої: впала більше ніж на X%, зʼявилась у наявності, зникла з
полиці. Історія — у вашу таблицю або CRM, звіт — на пошту чи в чат. Демо — не стеля.

## Title (ru)

PriceWatch: следит за ценами в нескольких магазинах и пингует в Telegram, как только цена упала

## Description (ru)

Бот следит за ценами и наличием товаров в нескольких магазинах одновременно и
присылает уведомление в Telegram в ту же минуту, когда цена изменилась или товар
пропал с полки. Ничего не нужно открывать и проверять руками, он работает сам.

Живой канал с уведомлениями: https://t.me/pricewatch_demo
Это не макет. Туда в реальном времени падают изменения цен и наличия по 15 товарам,
а каждое воскресенье — сводный график цен за неделю.

Цифры:
- 15 товаров, 25 пар «товар-магазин», два магазина (MOYO и Prom) в одном потоке
- проверка каждые 3 часа, автоматически
- 0 грн/мес на содержание (GitHub Actions, бесплатный тариф)
- уведомление в Telegram через секунду после изменения цены или наличия
- вся история проверок ложится в Google Таблицу, еженедельно — стильный график

Данные честные: если товара нет в наличии, я это показываю, а не рисую красивую
цену. Вот та самая история, открытая на просмотр: [SHEET_VIEW_URL]

Читаю даже магазины под защитой Cloudflare. Rozetka блокирует обычный скрапер
(HTTP 403), поэтому я подделываю TLS-отпечаток браузера Chrome и забираю публичные
цены без всякого браузера, за миллисекунды. Как это устроено, с доказательством
до и после: https://github.com/rakhimabdulkhanov-m/pricewatch/blob/main/BYPASS.md

Под вас настраивается так же: ваши товары, ваши магазины, цены конкурентов. Правила
уведомлений свои: упала больше чем на X%, появилась в наличии, пропала с полки.
История — в вашу таблицу или CRM, отчёт — на почту или в чат. Демо — не потолок.

## Title (en)

PriceWatch: tracks prices across several stores and pings Telegram the moment one drops

## Description (en)

A bot that watches prices and stock across several stores at once and sends a Telegram
alert the same minute a price changes or an item goes out of stock. Nothing to open or
check by hand, it runs itself.

Live alert channel: https://t.me/pricewatch_demo
Not a mockup. Real price and stock changes for 15 products land there in real time,
and every Sunday it posts a styled weekly price chart.

The numbers:
- 15 products, 25 product-store pairs, two stores (MOYO and Prom) in one flow
- checks every 3 hours, automatically
- $0/month to run (GitHub Actions, free tier)
- a Telegram alert a second after a price or stock change
- every check logged to a Google Sheet, a styled chart weekly

The data is honest: if an item is out of stock, I show that instead of drawing a nice
price. Here is that same history, open for viewing: [SHEET_VIEW_URL]

It reads even Cloudflare-protected stores. Rozetka blocks an ordinary scraper (HTTP
403), so I replay Chrome's TLS fingerprint and pull the public prices with no browser
at all, in milliseconds. How it works, with a before/after proof:
https://github.com/rakhimabdulkhanov-m/pricewatch/blob/main/BYPASS.md

Yours is set up the same way: your products, your stores, competitor prices. Your own
alert rules: dropped more than X%, back in stock, gone from the shelf. History into
your sheet or CRM, the report to email or chat. The demo is not the ceiling.

## Tags (FH catalog search)

моніторинг цін, парсинг, веб-скрапінг, автоматизація, telegram bot, відстеження цін конкурентів

## Cover + assets (pending ~26.07 full-week chart)

- Cover (the FH image): the APP. Hero = the real Sumi-e weekly chart (full 7-day
  window, rendered ~26.07) + title + one-line payoff ("pings you the moment a price
  drops"). uk (FH) + en (worldwide). Render via a cover HTML → headless Chrome,
  2160×2160, like case1/case2 cover-*.html. Reuse chartstyle palette/fonts.
- Gallery assets (Upwork/PPH/GitHub, not FH):
  - the weekly chart PNG (en + uk)
  - the bypass before/after card (publish-assets/rozetka_bypass_uk.png / rozetka_bypass_en.png)
  - a screenshot of the live channel with real alerts
  - a screenshot of the public Sheet history
- Groom before publish: pick the week window with the most visible movement;
  confirm the channel has a few clean real alerts (not just the seed message);
  set the Sheet share to "anyone with the link can view" and fill [SHEET_VIEW_URL].

## Publish checklist (~26.07)

1. Weekly chart: confirm weekly.yml posted the full 7-day chart to the channel Sun 26.07
   (or workflow_dispatch it once ≥7 days of history exist).
2. Render cover-uk / cover-en from the real chart (2160×2160).
3. Fill [SHEET_VIEW_URL], verify the channel + sheet are publicly viewable.
4. Publish the FH card (cover-uk, category per the bid), paste Title/Description (uk).
5. Update profile; add the en set + bypass card to Upwork/PPH when those go live.
