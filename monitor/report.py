"""Weekly price-report chart and caption builder for PriceWatch.

Public interface
----------------
build_chart(history, locale="en", out_path=None) -> Path
    Render a weekly price chart from history rows (as returned by
    sheets.get_history()) and save it as a PNG.  Returns the output path.

weekly_caption(history, locale="en") -> str
    Return an HTML-safe Telegram caption with the top-3 movers.

Entry point (run directly):
    python -m monitor.report
    Generates both en and uk PNGs.  EN PNG is posted to Telegram via
    notify.send_photo.  UK PNG is saved to publish-assets/ for the case cover.

History row dict shape (as returned by sheets.get_history):
    {
        "checked_at_utc": "2026-07-11T10:00:00Z",
        "store":          "moyo",
        "product_id":     "iphone-15-128",
        "name":           "Apple iPhone 15 128GB",
        "price_uah":      32999,
        "in_stock":       True,
    }
"""

from __future__ import annotations

import html
import warnings

# JetBrains Mono lacks certain Unicode space characters (U+2009 thin space).
# matplotlib falls back silently — suppress the noise.
warnings.filterwarnings(
    "ignore",
    message=r"Glyph .* missing from font",
    category=UserWarning,
)

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from monitor import chartstyle

# ---------------------------------------------------------------------------
# Unicode constants (match notify.py conventions)
# ---------------------------------------------------------------------------

_THIN = " "   # THIN SPACE — thousands separator
_MINUS = "−"  # MINUS SIGN
_ARROW = "→"  # RIGHTWARDS ARROW
_UAH = "₴"    # HRYVNIA SIGN
_UP = "▲"     # BLACK UP-POINTING TRIANGLE
_DOWN = "▼"   # BLACK DOWN-POINTING TRIANGLE
_ELLIPSIS = "…"  # HORIZONTAL ELLIPSIS

# ---------------------------------------------------------------------------
# Locale strings
# ---------------------------------------------------------------------------

# Month abbreviations for locale-aware x-axis date formatting.
_MONTHS: dict[str, list[str]] = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "uk": ["січ", "лют", "бер", "кві", "тра", "чер",
           "лип", "сер", "вер", "жов", "лис", "гру"],
}

_LOCALE: dict[str, dict[str, str]] = {
    "en": {
        "title": "PriceWatch · Weekly price report",
        "subtitle_full": "{start} – {end}",
        "subtitle_short": "First {n} days",
        "top_moves_label": "Top moves this week",
        "top_moves_label_short": "Top moves · first {n} days",
        "no_data": "No data",
        "out_of_stock": "out of stock",
        "back_in_stock": "back in stock",
        "caption_header": "PriceWatch · weekly report {start} – {end}",
        "caption_header_short": "PriceWatch · first {n} days",
        "caption_top3": "Top movers:",
        "y_axis_label": "change from start",
    },
    "uk": {
        "title": "PriceWatch · Тижневий звіт цін",
        "subtitle_full": "{start} – {end}",
        "subtitle_short": "Перші {n} днів",
        "top_moves_label": "Найбільші зміни тижня",
        "top_moves_label_short": "Топ змін · перші {n} днів",
        "no_data": "Немає даних",
        "out_of_stock": "немає в наявності",
        "back_in_stock": "знову в наявності",
        "caption_header": "PriceWatch · тижневий звіт {start} – {end}",
        "caption_header_short": "PriceWatch · перші {n} днів",
        "caption_top3": "Топ змін:",
        "y_axis_label": "зміна від початку",
    },
}


def _L(locale: str, key: str, **kwargs: object) -> str:
    """Look up a locale string and format it."""
    s = _LOCALE.get(locale, _LOCALE["en"]).get(key, _LOCALE["en"][key])
    return s.format(**kwargs) if kwargs else s


def _months(locale: str) -> list[str]:
    return _MONTHS.get(locale, _MONTHS["en"])


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------

def fmt_price(amount: float) -> str:
    """Format a price with thin-space thousands separator, integer rounding.

    Example: 32999 -> '32<U+2009>999'
    """
    s = str(int(round(amount)))
    groups: list[str] = []
    while len(s) > 3:
        groups.append(s[-3:])
        s = s[:-3]
    groups.append(s)
    return _THIN.join(reversed(groups))


def fmt_pct(old: float, new: float) -> str:
    """Return percent-change string.

    Negative uses true minus U+2212; positive uses '+'.
    One decimal place: (31499, 32999) -> '−4.5%'
    """
    pct = (new - old) / old * 100
    if pct < 0:
        return f"{_MINUS}{abs(pct):.1f}%"
    return f"+{pct:.1f}%"


def _fmt_pct_axis(v: float, _pos: object) -> str:
    """Y-axis tick formatter for percent-change mode."""
    if v == 0:
        return "0%"
    if v > 0:
        return f"+{v:.1f}%"
    return f"{_MINUS}{abs(v):.1f}%"


def _short_name(name: str, max_chars: int = 18) -> str:
    """Truncate *name* to *max_chars*, appending ellipsis if needed."""
    if len(name) <= max_chars:
        return name
    return name[: max_chars - 1] + _ELLIPSIS


# ---------------------------------------------------------------------------
# History parsing
# ---------------------------------------------------------------------------

class _SeriesPoint(NamedTuple):
    ts: datetime
    price: float


def _parse_ts(s: str) -> datetime:
    """Parse ISO-8601 UTC string to timezone-aware datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _build_series(
    history: list[dict],
) -> dict[tuple[str, str], list[_SeriesPoint]]:
    """Group history rows into per-(product_id, store) price series."""
    series: dict[tuple[str, str], list[_SeriesPoint]] = defaultdict(list)
    for row in history:
        key = (row["product_id"], row["store"])
        ts = _parse_ts(row["checked_at_utc"])
        series[key].append(_SeriesPoint(ts=ts, price=float(row["price_uah"])))
    for pts in series.values():
        pts.sort(key=lambda p: p.ts)
    return dict(series)


def _pct_change(pts: list[_SeriesPoint]) -> float:
    """Absolute percent change from first to last point."""
    if len(pts) < 2:
        return 0.0
    return abs((pts[-1].price - pts[0].price) / pts[0].price * 100)


def _select_top_movers(
    series: dict[tuple[str, str], list[_SeriesPoint]],
    n: int = 5,
) -> list[tuple[str, str]]:
    """Return up to *n* (product_id, store) keys sorted by absolute % change desc."""
    scored = [
        (key, _pct_change(pts))
        for key, pts in series.items()
        if len(pts) >= 2
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    limit = max(4, min(n, 6))
    return [k for k, _ in scored[:limit]]


def _window_info(history: list[dict]) -> tuple[datetime, datetime, int]:
    """Return (min_ts, max_ts, days_in_window)."""
    timestamps = [_parse_ts(r["checked_at_utc"]) for r in history]
    t_min = min(timestamps)
    t_max = max(timestamps)
    days = max(1, round((t_max - t_min).total_seconds() / 86400))
    return t_min, t_max, days


# ---------------------------------------------------------------------------
# Strip: top moves
# ---------------------------------------------------------------------------

def _top_moves_rows(
    series: dict[tuple[str, str], list[_SeriesPoint]],
    history: list[dict],
    max_rows: int = 3,
) -> list[tuple[tuple[str, str], list[_SeriesPoint]]]:
    """Return up to max_rows movers sorted by absolute % change."""
    scored = [
        (key, pts, _pct_change(pts))
        for key, pts in series.items()
        if len(pts) >= 2
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    return [(k, pts) for k, pts, _ in scored[:max_rows]]


def _name_for(key: tuple[str, str], history: list[dict]) -> str:
    """Look up the product name for (product_id, store) from raw history."""
    pid, store = key
    for row in history:
        if row["product_id"] == pid and row["store"] == store:
            return row["name"]
    return pid


# ---------------------------------------------------------------------------
# Label overlap nudging
# ---------------------------------------------------------------------------

def _nudge_labels(
    label_pts: list[tuple[float, float, float, str, str, float]],
    y_range: float,
    chart_h_px: float,
    font_pt: float = 7.0,
) -> list[tuple[float, float, float, str, str, float]]:
    """Nudge label y-positions to prevent vertical overlap.

    Parameters
    ----------
    label_pts:
        List of (pct_y, actual_price, last_ts_float, color, label_text, alpha)
        sorted ascending by pct_y.
    y_range:
        Data range in % units (y_max_plot - y_min_plot).
    chart_h_px:
        Chart axes height in pixels.
    font_pt:
        Font size in points used for labels.

    Returns
    -------
    Same list with pct_y adjusted.
    """
    font_h_px = font_pt * chartstyle.DPI / 72.0
    min_gap = (font_h_px / chart_h_px) * y_range * 1.4  # 40% safety margin

    result = list(label_pts)
    result.sort(key=lambda x: x[0])  # sort by pct_y ascending

    # Single bottom-to-top nudge pass.
    for i in range(1, len(result)):
        prev_y = result[i - 1][0]
        cur_y = result[i][0]
        if cur_y - prev_y < min_gap:
            result[i] = (prev_y + min_gap,) + result[i][1:]

    return result


# ---------------------------------------------------------------------------
# Main chart builder
# ---------------------------------------------------------------------------

def build_chart(
    history: list[dict],
    locale: str = "en",
    out_path: str | Path | None = None,
) -> Path:
    """Render weekly price chart from *history* rows.

    The y-axis plots percent change from the window start (all series begin at
    0%).  Right-edge direct labels show: short product name + actual price in
    UAH — giving comparable movement AND real price on one chart.

    Parameters
    ----------
    history:
        List of row dicts as returned by sheets.get_history().
    locale:
        'en' or 'uk'.
    out_path:
        Where to save the PNG.  Defaults to 'pricewatch_weekly_{locale}.png'
        in the current directory.

    Returns
    -------
    Path of the saved PNG.
    """
    if out_path is None:
        out_path = Path(f"pricewatch_weekly_{locale}.png")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not history:
        with chartstyle.style_context():
            fig, ax = plt.subplots(figsize=chartstyle.FIGSIZE, dpi=chartstyle.DPI)
            ax.text(0.5, 0.5, _L(locale, "no_data"),
                    ha="center", va="center",
                    transform=ax.transAxes,
                    fontproperties=chartstyle.fp_literata("semibold"),
                    color=chartstyle.INK_MUTED, fontsize=14)
            ax.axis("off")
            fig.savefig(out_path, dpi=chartstyle.DPI, facecolor=chartstyle.BG)
            plt.close(fig)
        return out_path

    t_min, t_max, days = _window_info(history)
    series = _build_series(history)
    top_keys = _select_top_movers(series, n=5)
    short_window = days < 7

    months = _months(locale)
    date_fmt_str = "%d %b"

    def _fmt_date_locale(ts_float: float, _pos: object) -> str:
        dt = mdates.num2date(ts_float)
        return f"{dt.day:02d} {months[dt.month - 1]}"

    start_str = f"{t_min.day:02d} {months[t_min.month - 1]}"
    end_str = f"{t_max.day:02d} {months[t_max.month - 1]}"

    accent_alphas = [1.0] + list(chartstyle.ALPHA_SERIES)

    with chartstyle.style_context():
        fig = plt.figure(figsize=chartstyle.FIGSIZE, dpi=chartstyle.DPI)

        # ----------------------------------------------------------------
        # Layout: explicit axes positions (figure fractions, y=0 at bottom).
        #   Title/subtitle: 0.89 – 1.0 (fig.text, not an axes)
        #   Chart:  left=0.08, bottom=0.22, width=0.67, height=0.66
        #           (top = 0.88; leaves 0.11 gap for x-tick labels above strip)
        #   Strip:  left=0.08, bottom=0.03, width=0.67, height=0.13
        #           (top = 0.16; x-tick labels fit in 0.16–0.22 gap = 54px)
        # ----------------------------------------------------------------
        ax_chart = fig.add_axes([0.08, 0.22, 0.67, 0.66])
        ax_strip = fig.add_axes([0.08, 0.03, 0.67, 0.13])

        # ----------------------------------------------------------------
        # Compute percent-change series for chart
        # ----------------------------------------------------------------
        # pre-pass: collect all pct values to set y-axis range
        all_pct_flat: list[float] = []
        series_pct: dict[tuple[str, str], list[float]] = {}
        for key in top_keys:
            pts = series[key]
            base = pts[0].price
            pcts = [(p.price - base) / base * 100 for p in pts]
            series_pct[key] = pcts
            all_pct_flat.extend(pcts)

        y_min_data = min(all_pct_flat)
        y_max_data = max(all_pct_flat)
        y_span = max(y_max_data - y_min_data, 2.0)  # at least 2% span
        y_pad = y_span * 0.12
        # Extra top headroom for right-edge labels (stacked vertically)
        n_labels = len(top_keys)
        label_font_pt = 7.0
        chart_h_px = 0.66 * chartstyle.FIGSIZE[1] * chartstyle.DPI
        font_h_px = label_font_pt * chartstyle.DPI / 72.0
        label_stack_pct = n_labels * (font_h_px / chart_h_px) * (y_span + 2 * y_pad) * 1.5
        y_min_plot = min(y_min_data - y_pad, -y_pad)
        y_max_plot = max(y_max_data + y_pad, y_pad) + label_stack_pct

        # ----------------------------------------------------------------
        # Plot lines + collect label points
        # ----------------------------------------------------------------
        label_pts: list[tuple[float, float, float, str, str, float]] = []
        # each entry: (pct_y, actual_price, last_ts_num, color, short_label, alpha)

        last_ts = max(p.ts for pts in series.values() for p in pts)
        last_ts_num = mdates.date2num(last_ts)

        for i, key in enumerate(top_keys):
            pts = series[key]
            pcts = series_pct[key]
            name = _name_for(key, history)

            times = [p.ts for p in pts]

            is_accent = i == 0
            color = chartstyle.ACCENT if is_accent else chartstyle.INK
            alpha = accent_alphas[i] if i < len(accent_alphas) else chartstyle.ALPHA_SERIES[-1]
            lw = chartstyle.LW_ACCENT if is_accent else chartstyle.LW_OTHER

            ax_chart.plot(
                times, pcts,
                color=color,
                alpha=alpha,
                linewidth=lw,
                solid_capstyle="round",
                solid_joinstyle="round",
                zorder=3 - i,
            )

            short = _short_name(name)
            label_text = f"{short}  {fmt_price(pts[-1].price)} {_UAH}"
            label_pts.append((pcts[-1], pts[-1].price, last_ts_num, color, label_text, alpha))

        ax_chart.set_ylim(y_min_plot, y_max_plot)
        # Ensure 0% baseline reference is visible
        ax_chart.axhline(0, color=chartstyle.SPINE_COLOR, linewidth=0.5, zorder=0)

        # ----------------------------------------------------------------
        # Place direct labels (nudged to prevent overlap)
        # ----------------------------------------------------------------
        y_range_plot = y_max_plot - y_min_plot
        nudged = _nudge_labels(label_pts, y_range_plot, chart_h_px, font_pt=label_font_pt)

        fp_label = chartstyle.fp_jetbrains("normal")
        fp_label.set_size(label_font_pt)

        for pct_y, actual_price, ts_num, color, label_text, alpha in nudged:
            ax_chart.annotate(
                label_text,
                xy=(ts_num, pct_y),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                color=color,
                alpha=min(1.0, alpha + 0.15),
                fontproperties=fp_label,
                clip_on=False,
                annotation_clip=False,
            )

        # ----------------------------------------------------------------
        # Chart axes styling
        # ----------------------------------------------------------------
        for spine_name in ("top", "right"):
            ax_chart.spines[spine_name].set_visible(False)
        for spine_name in ("left", "bottom"):
            ax_chart.spines[spine_name].set_color(chartstyle.SPINE_COLOR)

        # Y-axis: percent-change formatter
        ax_chart.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_pct_axis))
        for lbl in ax_chart.get_yticklabels():
            lbl.set_fontproperties(chartstyle.fp_jetbrains("normal"))
            lbl.set_fontsize(7)
            lbl.set_color(chartstyle.INK_MUTED)

        # X-axis: locale-aware date labels
        ax_chart.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_date_locale))
        ax_chart.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 6)))
        for lbl in ax_chart.get_xticklabels():
            lbl.set_fontproperties(chartstyle.fp_jetbrains("normal"))
            lbl.set_fontsize(7)
            lbl.set_color(chartstyle.INK_MUTED)
            lbl.set_rotation(0)

        ax_chart.tick_params(axis="both", which="both", length=3, color=chartstyle.SPINE_COLOR)

        # ----------------------------------------------------------------
        # Title and subtitle (figure-level text, not axes)
        # ----------------------------------------------------------------
        title_text = _L(locale, "title")
        subtitle_text = (
            _L(locale, "subtitle_short", n=days)
            if short_window
            else _L(locale, "subtitle_full", start=start_str, end=end_str)
        )

        fp_title = chartstyle.fp_literata("semibold")
        fp_title.set_size(13)
        fp_sub = chartstyle.fp_jetbrains("normal")
        fp_sub.set_size(8)

        fig.text(0.08, 0.95, title_text,
                 fontproperties=fp_title, color=chartstyle.INK,
                 ha="left", va="bottom", transform=fig.transFigure)
        fig.text(0.08, 0.905, subtitle_text,
                 fontproperties=fp_sub, color=chartstyle.INK_MUTED,
                 ha="left", va="bottom", transform=fig.transFigure)

        # ----------------------------------------------------------------
        # Bottom strip: top moves (absolute prices)
        # ----------------------------------------------------------------
        ax_strip.axis("off")
        for spine in ax_strip.spines.values():
            spine.set_visible(False)

        strip_moves = _top_moves_rows(series, history, max_rows=3)
        strip_label = (
            _L(locale, "top_moves_label_short", n=days)
            if short_window
            else _L(locale, "top_moves_label")
        )

        fp_strip_head = chartstyle.fp_literata("semibold")
        fp_strip_head.set_size(7.5)
        fp_strip_row = chartstyle.fp_jetbrains("normal")
        fp_strip_row.set_size(7)

        ax_strip.text(0.0, 1.0, strip_label,
                      transform=ax_strip.transAxes,
                      fontproperties=fp_strip_head,
                      color=chartstyle.INK, va="top", ha="left")

        for row_i, (key, pts) in enumerate(strip_moves):
            name = _name_for(key, history)
            old_p = pts[0].price
            new_p = pts[-1].price
            marker = _DOWN if new_p < old_p else _UP
            delta_color = chartstyle.RUST if new_p < old_p else chartstyle.GREEN

            full_row = (
                f"{marker} {name}  "
                f"{fmt_price(old_p)} {_ARROW} {fmt_price(new_p)} {_UAH}"
                f"  {fmt_pct(old_p, new_p)}"
            )

            # Row y-positions from top of strip: 0.70, 0.43, 0.16
            y = 0.72 - row_i * 0.27

            # Full row in INK, then overlay marker in semantic color.
            ax_strip.text(0.0, y, full_row,
                          transform=ax_strip.transAxes,
                          fontproperties=fp_strip_row,
                          color=chartstyle.INK, va="top", ha="left")
            ax_strip.text(0.0, y, marker,
                          transform=ax_strip.transAxes,
                          fontproperties=fp_strip_row,
                          color=delta_color, va="top", ha="left")

        fig.savefig(out_path, dpi=chartstyle.DPI, facecolor=chartstyle.BG)
        plt.close(fig)

    return out_path


# ---------------------------------------------------------------------------
# Caption builder
# ---------------------------------------------------------------------------

def weekly_caption(history: list[dict], locale: str = "en") -> str:
    """Return HTML-safe Telegram caption with top-3 movers.

    Uses U+2009 thin space as thousands separator and U+2212 true minus.
    No em dash anywhere.
    """
    if not history:
        return html.escape(_L(locale, "no_data"))

    t_min, t_max, days = _window_info(history)
    series = _build_series(history)
    short_window = days < 7

    months = _months(locale)
    start_str = f"{t_min.day:02d} {months[t_min.month - 1]}"
    end_str = f"{t_max.day:02d} {months[t_max.month - 1]}"

    header = (
        _L(locale, "caption_header_short", n=days)
        if short_window
        else _L(locale, "caption_header", start=start_str, end=end_str)
    )

    lines = [f"<b>{html.escape(header)}</b>"]

    top3_moves = _top_moves_rows(series, history, max_rows=3)
    if top3_moves:
        lines.append(html.escape(_L(locale, "caption_top3")))
        for key, pts in top3_moves:
            name = _name_for(key, history)
            old_p = pts[0].price
            new_p = pts[-1].price
            marker = _DOWN if new_p < old_p else _UP
            row = (
                f"{marker} {html.escape(name)}  "
                f"{fmt_price(old_p)} {_ARROW} {fmt_price(new_p)} {_UAH}  "
                f"{fmt_pct(old_p, new_p)}"
            )
            lines.append(row)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from monitor import notify, sheets

    history = sheets.get_history(days=7)
    if not history:
        print(
            "[report] get_history returned None or empty — nothing to post",
            file=sys.stderr,
        )
        sys.exit(0)

    # EN chart: render and post to Telegram.
    en_path = build_chart(history, locale="en", out_path="pricewatch_weekly_en.png")
    print(f"[report] EN chart: {en_path.resolve()}")

    caption = weekly_caption(history, locale="en")
    ok = notify.send_photo(en_path, caption)
    if ok:
        print("[report] EN chart posted to Telegram")
    else:
        print("[report] send_photo failed (see stderr for details)", file=sys.stderr)

    # UK chart: save to publish-assets/ for case cover — no Telegram post.
    uk_dir = Path("publish-assets")
    uk_dir.mkdir(exist_ok=True)
    uk_path = build_chart(
        history, locale="uk",
        out_path=uk_dir / "pricewatch_weekly_uk.png",
    )
    print(f"[report] UK chart: {uk_path.resolve()}")
