"""Render the Rozetka Cloudflare-bypass portfolio card (before/after).

Client-facing visual for non-technical clients who will not run the demo:
a single square image showing plain Python blocked (403) vs Chrome-TLS
impersonation returning live prices. Warm-editorial "Sumi-e" style, reusing
monitor/chartstyle fonts + palette so it sits with the weekly chart.

Outputs (2000x2000):
    rozetka_bypass_en.png                 (worldwide)
    publish-assets/rozetka_bypass_uk.png  (Freelancehunt card)

Data is the live 2026-07-22 demo run (scripts/rozetka_demo.py).
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from monitor.chartstyle import (  # noqa: E402
    ACCENT, BG, GREEN, INK, INK_MUTED, SPINE_COLOR,
    fp_jetbrains, fp_literata,
)

# Live demo data (price in UAH, short name).
BYPASSED = [
    (65299, "Galaxy S26 Ultra"),
    (56099, "Galaxy S26+ 512GB"),
    (59999, "iPhone 17 Pro 256GB"),
    (61999, "iPhone 17 Pro 256GB"),
]

STR = {
    "en": {
        "title": "Getting past Cloudflare",
        "subtitle": "Live Rozetka prices · public product data",
        "left_head": "Plain Python · httpx",
        "right_head": "Chrome TLS · curl_cffi",
        "blocked": "HTTP 403",
        "wall": "Cloudflare wall",
        "instock": "in stock",
        "caption": ("Same URL, same IP. curl_cffi replays Chrome’s TLS "
                    "fingerprint,\nso Cloudflare’s passive check passes "
                    "— no browser, milliseconds."),
        "badge": "case 3 · PriceWatch",
    },
    "uk": {
        "title": "Обхід Cloudflare",
        "subtitle": "Живі ціни Rozetka · публічні дані товарів",
        "left_head": "Звичайний Python · httpx",
        "right_head": "Chrome TLS · curl_cffi",
        "blocked": "HTTP 403",
        "wall": "стіна Cloudflare",
        "instock": "в наявності",
        "caption": ("Той самий URL, той самий IP. curl_cffi "
                    "відтворює TLS-відбиток Chrome,\n"
                    "і пасивна перевірка Cloudflare проходить "
                    "— без браузера, мілісекунди."),
        "badge": "case 3 · PriceWatch",
    },
}


def _price(n: int) -> str:
    return format(n, ",d").replace(",", chr(32)) + " ₴"


def render(lang: str, out: Path) -> None:
    t = STR[lang]
    fig = plt.figure(figsize=(10, 10), dpi=200)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    # Title block
    ax.text(0.07, 0.92, t["title"], fontproperties=fp_literata("Bold"),
            fontsize=40, color=INK, va="top")
    ax.text(0.07, 0.855, t["subtitle"], fontproperties=fp_literata("Regular"),
            fontsize=19, color=INK_MUTED, va="top")

    # Divider
    ax.plot([0.07, 0.93], [0.82, 0.82], color=SPINE_COLOR, lw=1.5)

    # Column headers
    lx, rx = 0.09, 0.545
    ax.text(lx, 0.77, t["left_head"], fontproperties=fp_jetbrains("SemiBold"),
            fontsize=17, color=INK_MUTED, va="top")
    ax.text(rx, 0.77, t["right_head"], fontproperties=fp_jetbrains("SemiBold"),
            fontsize=17, color=INK, va="top")
    # Vertical separator between panels
    ax.plot([0.515, 0.515], [0.20, 0.75], color=SPINE_COLOR, lw=1.2)

    y = 0.70
    dy = 0.115
    for price, name in BYPASSED:
        # LEFT: blocked
        ax.text(lx, y, "✕", fontproperties=fp_jetbrains("SemiBold"),
                fontsize=20, color=ACCENT, va="center")
        ax.text(lx + 0.045, y + 0.012, t["blocked"],
                fontproperties=fp_jetbrains("SemiBold"), fontsize=19,
                color=ACCENT, va="center")
        ax.text(lx + 0.045, y - 0.028, t["wall"],
                fontproperties=fp_jetbrains("Regular"), fontsize=13,
                color=INK_MUTED, va="center")
        # RIGHT: bypassed + price
        ax.text(rx, y, "✓", fontproperties=fp_jetbrains("SemiBold"),
                fontsize=20, color=GREEN, va="center")
        ax.text(rx + 0.045, y + 0.014, _price(price),
                fontproperties=fp_literata("SemiBold"), fontsize=23,
                color=INK, va="center")
        ax.text(rx + 0.045, y - 0.028,
                f"200 · {name} · {t['instock']}",
                fontproperties=fp_jetbrains("Regular"), fontsize=11,
                color=INK_MUTED, va="center")
        y -= dy

    # Caption band
    ax.plot([0.07, 0.93], [0.175, 0.175], color=SPINE_COLOR, lw=1.5)
    ax.text(0.07, 0.135, t["caption"], fontproperties=fp_jetbrains("Regular"),
            fontsize=14.5, color=INK, va="top", linespacing=1.5)
    ax.text(0.93, 0.05, t["badge"], fontproperties=fp_literata("SemiBold"),
            fontsize=15, color=ACCENT, va="center", ha="right")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    print(f"wrote {out}  ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    render("en", root / "rozetka_bypass_en.png")
    render("uk", root / "publish-assets" / "rozetka_bypass_uk.png")
