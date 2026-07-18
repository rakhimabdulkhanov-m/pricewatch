"""Sumi-e chart style for PriceWatch weekly reports.

Public interface
----------------
apply_style()
    Apply rcParams globally (call once at module import or before a figure).

style_context()
    Context manager that applies the style and restores previous rcParams on exit.

Color constants
---------------
BG          figure and axes background
INK         primary text and line color
INK_MUTED   secondary / muted text
GRID_COLOR  y-axis grid line color
SPINE_COLOR axes spine color
ACCENT      rust red: highlighted series and key deltas only
GREEN       semantic up-arrow color
RUST        semantic down-arrow color (alias for ACCENT)
ALPHA_SERIES  (0.85, 0.55, 0.35) alpha values for non-accent series

Font helpers
------------
fp_literata(weight)     -> matplotlib.font_manager.FontProperties
fp_jetbrains(weight)    -> matplotlib.font_manager.FontProperties
    weight: 'normal' (400), 'semibold' (600), 'bold' (700)
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager

# ---------------------------------------------------------------------------
# Font registration — happens once at import time
# ---------------------------------------------------------------------------

_FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"

_FONT_FILES = [
    "Literata-Regular.ttf",
    "Literata-SemiBold.ttf",
    "Literata-Bold.ttf",
    "JetBrainsMono-Regular.ttf",
    "JetBrainsMono-SemiBold.ttf",
]

for _fname in _FONT_FILES:
    _fpath = _FONTS_DIR / _fname
    if _fpath.exists():
        fontManager.addfont(str(_fpath))

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

BG = "#F4F1EA"           # figure + axes background (warm paper)
INK = "#26241F"          # primary text / line ink
INK_MUTED = "#5C574C"    # muted text (subtitle, tick labels secondary)
GRID_COLOR = "#928B7A"   # y-axis grid
SPINE_COLOR = "#D8D1C0"  # left + bottom spines

ACCENT = "#B23A2C"       # rust red: highlighted series and negative delta marker
GREEN = "#6B8A5A"        # semantic up / positive delta marker
RUST = ACCENT            # alias kept for clarity in delta formatting

# Alpha progression for non-accent series (primary, secondary, tertiary)
ALPHA_SERIES = (0.85, 0.55, 0.35)

# ---------------------------------------------------------------------------
# Line widths
# ---------------------------------------------------------------------------

LW_ACCENT = 2.0
LW_OTHER = 1.4

# ---------------------------------------------------------------------------
# Figure geometry
# ---------------------------------------------------------------------------

FIGSIZE = (8, 4.5)
DPI = 200  # 1600 x 900 px output

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

_LITERATA_WEIGHTS: dict[str, str] = {
    "normal": "normal",
    "regular": "normal",
    "semibold": "semibold",
    "600": "semibold",
    "bold": "bold",
    "700": "bold",
}

_JBM_WEIGHTS: dict[str, str] = {
    "normal": "normal",
    "regular": "normal",
    "semibold": "semibold",
    "600": "semibold",
}


def fp_literata(weight: str = "normal") -> FontProperties:
    """Return FontProperties for Literata at the given weight.

    Accepted weight strings: 'normal', 'regular', 'semibold', '600', 'bold', '700'.
    Falls back to system sans-serif if the font is not registered.
    """
    w = _LITERATA_WEIGHTS.get(weight.lower(), "normal")
    return FontProperties(family="Literata", weight=w)


def fp_jetbrains(weight: str = "normal") -> FontProperties:
    """Return FontProperties for JetBrains Mono at the given weight.

    Accepted weight strings: 'normal', 'regular', 'semibold', '600'.
    Falls back to monospace if the font is not registered.
    """
    w = _JBM_WEIGHTS.get(weight.lower(), "normal")
    return FontProperties(family="JetBrains Mono", weight=w)


# ---------------------------------------------------------------------------
# rcParams dict (reusable for both apply_style() and the context manager)
# ---------------------------------------------------------------------------

def _build_rcparams() -> dict:
    return {
        # Figure
        "figure.facecolor": BG,
        "figure.figsize": list(FIGSIZE),
        "figure.dpi": DPI,

        # Axes
        "axes.facecolor": BG,
        "axes.edgecolor": SPINE_COLOR,
        "axes.labelcolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": True,
        "axes.spines.bottom": True,
        "axes.linewidth": 0.8,

        # Grid: y-axis only
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID_COLOR,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.6,
        "grid.linestyle": "-",

        # Tick
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.pad": 4,
        "ytick.major.pad": 4,
        "xtick.bottom": True,
        "ytick.left": True,

        # Text
        "text.color": INK,

        # Lines
        "lines.linewidth": LW_OTHER,
        "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",

        # No fancy effects
        "path.effects": [],
        "axes.axisbelow": True,

        # Font: fall back to sans / mono in case font files missing
        "font.family": "sans-serif",
        "font.sans-serif": ["Literata", "DejaVu Sans", "Helvetica", "Arial"],
    }


# ---------------------------------------------------------------------------
# Public: apply_style()
# ---------------------------------------------------------------------------

def apply_style() -> None:
    """Apply sumi-e style to matplotlib rcParams globally."""
    mpl.rcParams.update(_build_rcparams())


# ---------------------------------------------------------------------------
# Public: style_context()
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def style_context():
    """Context manager that applies the sumi-e style and restores previous rcParams."""
    with mpl.rc_context(_build_rcparams()):
        yield
