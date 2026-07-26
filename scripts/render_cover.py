"""Render the Freelancehunt portfolio cover for Case 3 (PriceWatch).

The FH card takes exactly ONE image, so the cover has to carry the whole pitch:
what it is, the real weekly chart as proof, and the numbers that kill the
"what does it cost to keep running" objection.

Pipeline:
  1. render the real weekly chart from live Sheet history (monitor.report)
  2. crop off the chart's own title block — the cover supplies its own headline
  3. render publish-assets/cover-{locale}.html through headless Chrome at
     1080x1080 and again at device-scale 2 for the 2160x2160 upload

Usage:
    python scripts/render_cover.py            # both locales, live data
    python scripts/render_cover.py --no-fetch # reuse the last chart crops

Outputs (publish-assets/):
    cover-uk.png / cover-uk-2x.png
    cover-en.png / cover-en-2x.png
    cover-chart-uk.png / cover-chart-en.png   (intermediate crops)
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = ROOT / "publish-assets"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

# The chart PNG is 1600x900 with its own title band on top, a right-hand label
# column and a top-moves strip at the bottom. Shrunk to cover width those all
# turn into unreadable 4pt mush, so the cover keeps only the plot area (the
# shape of the week) and restates the headline number in cover-sized type.
CHART_BOX = (0.0, 0.115, 0.755, 0.826)  # left, top, right, bottom (fractions)


def render_charts() -> dict[str, dict[str, str]]:
    """Render the weekly chart from live Sheet history; return cover facts."""
    from monitor import envfile, report, sheets

    envfile.load_dotenv(str(ROOT / ".env"))
    history = sheets.get_history(days=56)
    if not history:
        raise SystemExit("[cover] no history from the Sheets webhook")

    now = datetime.now(timezone.utc)
    facts: dict[str, dict[str, str]] = {}
    for locale in ("uk", "en"):
        raw = ASSETS / f"cover-chart-{locale}-raw.png"
        report.build_chart(history, locale=locale, out_path=raw, now=now)
        crop_chart(raw, ASSETS / f"cover-chart-{locale}.png")
        raw.unlink()
        facts[locale] = top_mover(history, locale, now)
    print("[cover] charts rendered from live history")
    return facts


def top_mover(history: list, locale: str, now: datetime) -> dict[str, str]:
    """Headline number for the cover: biggest mover of the reported week.

    Pulled from the same live history the chart is drawn from, so the cover
    cannot drift out of sync with the channel post.
    """
    from monitor import report

    t_min, t_max, _days, _full = report._window_info(history, 7, now)
    series = report._clip_series(report._build_series(history), t_min, t_max)
    rows = report._top_moves_rows(series, history, max_rows=1)
    if not rows:
        return {"mover": "", "range": ""}

    key, pts = rows[0]
    # Store titles trail article codes and seller tags ("JBLT720BTWHT mars")
    # that would push the headline off the cover — cut to the model name.
    name = report._short_name(report._brand_name(report._name_for(key, history)), 20)
    old_p, new_p = pts[0].price, pts[-1].price
    marker = "▼" if new_p < old_p else "▲"
    months = report._months(locale)
    rng = (f"{t_min.day:02d} {months[t_min.month - 1]} – "
           f"{t_max.day:02d} {months[t_max.month - 1]}")
    return {
        "mover": (f"{marker} {name}  {report.fmt_price(old_p)} → "
                  f"{report.fmt_price(new_p)} ₴  "
                  f"{report.fmt_pct(old_p, new_p)}"),
        "range": rng,
    }


def crop_chart(src: Path, dst: Path) -> None:
    """Keep the plot area only — see CHART_BOX."""
    img = Image.open(src)
    w, h = img.size
    left, top, right, bottom = CHART_BOX
    img.crop((int(w * left), int(h * top),
              int(w * right), int(h * bottom))).save(dst)


def fill_template(locale: str, facts: dict[str, str]) -> Path:
    """Substitute the live numbers into the cover template."""
    tpl = (ASSETS / f"cover-{locale}.html").read_text(encoding="utf-8")
    filled = (tpl
              .replace("{{MOVER}}", facts.get("mover", ""))
              .replace("{{RANGE}}", facts.get("range", "")))
    out = ASSETS / f"cover-{locale}.filled.html"
    out.write_text(filled, encoding="utf-8")
    return out


def render_cover(locale: str, facts: dict[str, str]) -> None:
    page = fill_template(locale, facts)
    for scale, suffix in ((1, ""), (2, "-2x")):
        out = ASSETS / f"cover-{locale}{suffix}.png"
        subprocess.run(
            [
                str(CHROME),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--default-background-color=00000000",
                f"--force-device-scale-factor={scale}",
                "--window-size=1080,1080",
                f"--screenshot={out}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        size = Image.open(out).size
        print(f"[cover] {out.name}: {size[0]}x{size[1]}")


if __name__ == "__main__":
    import json

    cache = ASSETS / "cover-facts.json"
    if "--no-fetch" in sys.argv:
        all_facts = json.loads(cache.read_text(encoding="utf-8"))
    else:
        all_facts = render_charts()
        cache.write_text(json.dumps(all_facts, ensure_ascii=False, indent=2),
                         encoding="utf-8")

    for loc in ("uk", "en"):
        print(f"[cover] {loc} headline: {all_facts[loc]['mover']}")
        render_cover(loc, all_facts[loc])
