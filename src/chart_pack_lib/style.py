"""
Shared visual style for the QSR LHI chart pack.

This module ONLY renders charts from existing analysis/output CSVs and
dashboard/data JSON. It does not read, write, or alter any file under
analysis/, dashboard/, or the pipeline's own output directory.

Palette and typography combine BCG analytical storytelling + McKinsey
restraint + Tableau/Power BI readability + R/ggplot2 statistical
discipline, per the approved visual-direction brief. Grounded in actual
reference material inspected this session (not copied):
  - McKinsey Design System PDF (cdn.mckinsey.com) -- real tokens: McKinsey
    Deep Blue (near-black navy), Electric Blue #2251FF, a 4px spacing
    grid, and WCAG-AA-compliant semantic alert colours (warning amber,
    danger red, success green, info blue). This is a UI component system
    (buttons/alerts/cards), not a chart-design spec -- its colour
    discipline transfers, its literal component patterns do not.
  - BCG Data Visualization (rarevolume.com/work/bcg-dataviz) -- real
    pattern: oversized "big number" call-outs, bold inline emphasis
    words inside sentence-style headlines, one dominant colour family
    per exhibit, minimal decoration.
  - An actual Bain & Company report chart, Bain Corporate M&A Report
    2020 fig. 2.5 (bain.com) -- real pattern: a small coloured "Figure
    N" kicker before an insight-led title, direct end-of-series labels
    with leader lines INSTEAD OF a legend box, and literally zero
    gridlines where direct labels already carry the values.
None of these firms' literal branding (BCG's dark green, Bain's red as
a primary data colour, McKinsey's Electric Blue) is reused directly --
red in particular stays reserved for Critical Risk only, per this
project's own colour-communicates-risk rule. Cambria/Calibri remain the
house fonts (McKinseySans is not available and switching now would
break consistency with the rest of this project's deliverables).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ---------------------------------------------------------------- palette
INK = "#141f28"             # near-navy charcoal (McKinsey Deep Blue family, muted)
TEXT_DIM = "#57626d"
TEXT_FAINT = "#8b93a0"
BORDER = "#dcd9d2"
GRID = "#e7e4dd"

ACCENT = "#2e6b78"          # muted blue-teal: neutral / methodology series
ACCENT_SOFT = "#e6eef0"
NEUTRAL_GREY = "#9aa2ad"    # LEAKY / background / non-selected series
POPULATION_WASH = "#c9c4b8"  # very light neutral for an unhighlighted background population layer

RISK_COLORS = {
    "Healthy": "#2e7d5b",
    "Watch": "#bf8b2e",
    "High Risk": "#c1652e",
    "Critical Risk": "#ab3a2e",   # restrained brick-red, not saturated crimson
}
RISK_ORDER = ["Healthy", "Watch", "High Risk", "Critical Risk"]

PRIORITY_COLORS = {
    "Low": "#2e7d5b",
    "Medium": "#bf8b2e",
    "High": "#c1652e",
    "Critical": "#ab3a2e",
}
PRIORITY_ORDER = ["Low", "Medium", "High", "Critical"]

# Non-risk sequential ramps -- for metrics that are NOT a location's risk
# classification (e.g. how many distinct bands a business reached under
# stress-testing, or confidence/evidence level) but still want a light-to-dark
# "more/worse" visual progression. Built from the house accent teal so they
# read as "this project's palette," never from the reserved risk hues.
ACCENT_RAMP = ["#a9c7cc", "#2e6b78", "#16333a"]     # light teal -> ACCENT -> deep teal
CONFIDENCE_COLORS = {"High": "#2e6b78", "Medium": "#8fb3ba", "Low": "#c9c4b8"}
CONFIDENCE_ORDER = ["High", "Medium", "Low"]

FONT_DISPLAY = "Cambria"
FONT_BODY = "Calibri"
FONT_MONO = "Consolas"


def _register_fonts():
    for name in (FONT_DISPLAY, FONT_BODY, FONT_MONO):
        try:
            fm.findfont(name, fallback_to_default=False)
        except Exception:
            pass


_register_fonts()


def apply_base_rc():
    plt.rcParams.update({
        "font.family": FONT_BODY,
        "font.size": 11,
        "text.color": INK,
        "axes.edgecolor": TEXT_FAINT,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "xtick.color": TEXT_DIM,
        "ytick.color": TEXT_DIM,
        "axes.linewidth": 0.8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "svg.fonttype": "none",
    })


def clean_axes(ax, y_grid=True, x_grid=False):
    """House gridline/spine treatment: horizontal gridlines only, no plot border box.
    Gridlines are intentionally very light (Bain fig. 2.5 shows none at all where
    direct labels already carry the values) -- call with y_grid=False on any chart
    that already labels its bars/points directly."""
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_visible(True)
    ax.spines["bottom"].set_visible(True)
    ax.spines["left"].set_color(TEXT_FAINT)
    ax.spines["bottom"].set_color(TEXT_FAINT)
    ax.grid(False)
    if y_grid:
        ax.yaxis.grid(True, color=GRID, linewidth=0.6, zorder=0)
    if x_grid:
        ax.xaxis.grid(True, color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)


def kicker(fig, label, x=0.02, y=0.99):
    """Small coloured 'FIGURE N' kicker above the insight title -- the Bain
    fig.-number convention, in the house accent colour rather than a firm's
    literal brand red."""
    fig.text(x, y, label.upper(), fontsize=9.5, fontweight="bold", color=ACCENT,
              fontfamily=FONT_BODY, ha="left", va="top")


def title(ax, text, size=14, y=1.04):
    ax.set_title(text, fontsize=size, fontfamily=FONT_DISPLAY, fontweight="bold",
                 color=INK, loc="left", y=y, pad=6)


def source_note(fig, text, y=0.01):
    fig.text(0.02, y, text, fontsize=8, color=TEXT_FAINT, fontfamily=FONT_BODY,
              style="italic")


def end_label(ax, x, y, text, color=None, fontsize=10, ha="left", va="center", weight="bold"):
    """Direct end-of-series label -- used in place of a legend wherever a series
    has an obvious single end point to label (Bain fig. 2.5 pattern)."""
    ax.text(x, y, text, color=color or INK, fontsize=fontsize, fontweight=weight,
             fontfamily=FONT_BODY, ha=ha, va=va)


def savefig(fig, path, dpi=200):
    fig.savefig(path, dpi=dpi, bbox_inches="tight", pad_inches=0.28)
    plt.close(fig)
    print("wrote", path)


def teal_sequential_cmap():
    """House-derived sequential colormap (white -> ACCENT teal -> deep teal) for
    density/heatmap encodings, in place of matplotlib's generic 'Blues'."""
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("house_teal", ["#ffffff", ACCENT, "#12262b"])
