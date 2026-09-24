"""
Builds the final animated executive PPTX from chart_pack/_lib/deck_content.py.

Does NOT read, write, or alter anything under chart_pack/technical_report/,
chart_pack/pptx/, chart_pack/shared/, chart_pack/appendix/, analysis/, or dashboard/
except to read the single frozen image chart_pack/shared/fig_11_intervention_priority_quadrant_final.png
as a static picture (Slide 8, hybrid per the approved storyboard).

Native PowerPoint shapes throughout (rectangles, text boxes, lines) so PowerPoint's own
Morph / Wipe / Fade can drive the motion. See deck_anim.py for the transition/timing
implementation notes and its documented risk profile.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

import deck_content as C
from deck_anim import set_transition, TimingBuilder

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "chart_pack" / "deck"
OUT_DIR.mkdir(exist_ok=True)

EMU_PER_IN = 914400


def rgb(hexstr):
    return RGBColor.from_string(hexstr)


def new_deck():
    prs = Presentation()
    prs.slide_width = Emu(int(C.SLIDE_W_IN * EMU_PER_IN))
    prs.slide_height = Emu(int(C.SLIDE_H_IN * EMU_PER_IN))
    return prs


def blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def set_bg_white(slide):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb(C.WHITE)


def no_line(shape):
    shape.line.fill.background()


def solid_fill(shape, hexstr):
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(hexstr)
    no_line(shape)


def add_textbox(slide, text, left, top, width, height, size, color, bold=False,
                 italic=False, font=C.FONT_BODY, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
                 name=None, line_spacing=1.0, letter_spacing=False):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        r = p.add_run()
        r.text = line
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.name = font
        r.font.color.rgb = rgb(color)
    return tb


def add_kicker(slide, text):
    return add_textbox(slide, text, 0.7, 0.42, 10.0, 0.3, 11, C.ACCENT, bold=True,
                        font=C.FONT_BODY, name="Kicker")


def add_title(slide, text, size=None, width=11.9):
    if size is None:
        size = 20 if len(text) > 95 else (23 if len(text) > 60 else 27)
    return add_textbox(slide, text, 0.7, 0.75, width, 1.55, size, C.INK, bold=True,
                        font=C.FONT_DISPLAY, line_spacing=1.08, name="Title")


def add_source(slide, text):
    return add_textbox(slide, text, 0.7, 7.05, 11.9, 0.35, 9.5, C.TEXT_FAINT, italic=True,
                        name="Source")


def add_rect(slide, left, top, width, height, hexcolor, name=None):
    r = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    solid_fill(r, hexcolor)
    r.shadow.inherit = False
    if name:
        r.name = name
    return r


def add_line(slide, x1, y1, x2, y2, hexcolor, width_pt=1.25, dash=None, name=None):
    ln = slide.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    ln.line.color.rgb = rgb(hexcolor)
    ln.line.width = Pt(width_pt)
    if dash:
        d = ln.line._get_or_add_ln()
        pd = d.makeelement(qn("a:prstDash"), {"val": dash})
        d.append(pd)
    if name:
        ln.name = name
    return ln


# ---------------------------------------------------------------------------
# SLIDE 1 -- Risk-band distribution (Morph pair)
# ---------------------------------------------------------------------------
def build_slide1(prs):
    d = C.SLIDE_1
    bars = d["bars"]
    track_x = 3.35
    track_w_max = 7.1
    bar_h = 0.62
    gap = 0.28
    top0 = 2.55
    max_count = max(b[1] for b in bars)

    def make(state):
        s = blank_slide(prs)
        set_bg_white(s)
        add_kicker(s, d["kicker"])
        add_title(s, d["title"], width=8.6)
        add_source(s, d["source"])
        for i, (label, count, pct, color) in enumerate(bars):
            y = top0 + i * (bar_h + gap)
            add_textbox(s, label, 0.7, y, track_x - 0.85, bar_h, 15, C.INK, bold=False,
                        anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.LEFT, name=f"CatLabel_{label}")
            w = track_w_max * (count / max_count)
            if state == "a":
                bw = 0.04
                bar_color = C.NEUTRAL_GREY
            else:
                bw = w
                bar_color = color
            add_rect(s, track_x, y, bw, bar_h, bar_color, name=f"Bar_{label}")
            if state == "b":
                add_textbox(s, f"{count:,}  ({pct}%)", track_x + w + 0.15, y, 1.9, bar_h, 15,
                            C.INK, bold=True, anchor=MSO_ANCHOR.MIDDLE, name=f"Value_{label}")
        if state == "b":
            add_rect(s, 9.6, 0.75, 2.85, 0.85, C.ACCENT_SOFT, name="CalloutBox")
            add_textbox(s, d["key_number"], 9.8, 0.80, 2.45, 0.42, 26, C.ACCENT, bold=True,
                        font=C.FONT_DISPLAY, name="CalloutNum")
            add_textbox(s, d["key_number_label"], 9.8, 1.20, 2.5, 0.35, 10, C.TEXT_DIM,
                        name="CalloutLbl")
        return s

    sa = make("a")
    sb = make("b")
    set_transition(sa, "fade")
    set_transition(sb, "morph")
    return sa, sb


# ---------------------------------------------------------------------------
# SLIDE 2 -- LEAKY vs SAFE (Morph pair)
# ---------------------------------------------------------------------------
def build_slide2(prs):
    d = C.SLIDE_2
    naive_label, naive_val, naive_color = d["bars"][0]
    safe_label, safe_val, safe_color = d["bars"][1]
    axis_bottom = 5.85
    chart_h = 3.35
    scale_max = 1.15  # headroom above the 0-1 AUC scale so bar tops never reach the title
    bar_w = 1.9
    x_naive = 4.15
    x_safe = 7.55

    def val_to_h(v):
        return chart_h * (v / scale_max)

    def make(state):
        s = blank_slide(prs)
        set_bg_white(s)
        add_kicker(s, d["kicker"])
        add_title(s, d["title"], size=20)
        add_source(s, d["source"])
        add_line(s, 3.6, axis_bottom, 10.8, axis_bottom, C.TEXT_FAINT, width_pt=1.25, name="AxisLine")
        base_y = axis_bottom - val_to_h(d["baseline"])
        add_line(s, 3.6, base_y, 10.8, base_y, C.TEXT_FAINT, width_pt=1.0, dash="dash", name="BaselineLine")
        add_textbox(s, d["baseline_label"], 10.9, base_y - 0.15, 1.8, 0.3, 10, C.TEXT_FAINT,
                    name="BaselineLbl")
        add_textbox(s, naive_label, x_naive - 0.55, axis_bottom + 0.12, bar_w + 1.1, 0.5, 12,
                    C.TEXT_DIM, align=PP_ALIGN.CENTER, name="AxisCatNaive")
        add_textbox(s, safe_label, x_safe - 0.55, axis_bottom + 0.12, bar_w + 1.1, 0.5, 12,
                    C.TEXT_DIM, align=PP_ALIGN.CENTER, name="AxisCatSafe")

        h_naive = val_to_h(naive_val)
        add_rect(s, x_naive, axis_bottom - h_naive, bar_w, h_naive, naive_color, name="Bar_Naive")
        add_textbox(s, f"{naive_val:.3f}", x_naive - 0.3, axis_bottom - h_naive - 0.55, bar_w + 0.6,
                    0.5, 30, C.INK, bold=True, font=C.FONT_DISPLAY, align=PP_ALIGN.CENTER,
                    name="Number_Naive")

        if state == "a":
            h_safe = 0.02
        else:
            h_safe = val_to_h(safe_val)
        add_rect(s, x_safe, axis_bottom - h_safe, bar_w, h_safe, safe_color, name="Bar_Safe")

        if state == "b":
            add_textbox(s, f"{safe_val:.3f}", x_safe - 0.3, axis_bottom - h_safe - 0.55, bar_w + 0.6,
                        0.5, 30, C.INK, bold=True, font=C.FONT_DISPLAY, align=PP_ALIGN.CENTER,
                        name="Number_Safe")
            gap_mid_y = (min(axis_bottom - h_naive, axis_bottom - h_safe) + axis_bottom) / 2
            add_textbox(s, d["drop_label"], (x_naive + bar_w + x_safe) / 2 - 0.65, gap_mid_y - 0.2, 1.3,
                        0.4, 17, C.RISK_COLORS["Critical Risk"], bold=True, font=C.FONT_DISPLAY,
                        align=PP_ALIGN.CENTER, name="DropLabel")
            add_textbox(s, "Every number after this has been checked for this", 3.6, 6.68,
                        7.2, 0.3, 13, C.TEXT_DIM, italic=False, name="Caption")
        return s

    sa = make("a")
    sb = make("b")
    set_transition(sa, "fade")
    set_transition(sb, "morph")
    return sa, sb


# ---------------------------------------------------------------------------
# SLIDE 3 -- SHAP drivers (single slide, staggered Wipe)
# ---------------------------------------------------------------------------
def build_slide3(prs):
    d = C.SLIDE_3
    s = blank_slide(prs)
    set_bg_white(s)
    add_kicker(s, d["kicker"])
    add_title(s, d["title"])
    add_source(s, d["source"])

    bars = d["bars"]
    track_x = 4.55
    track_w_max = 6.6
    bar_h = 0.5
    gap = 0.175
    top0 = 2.35
    max_val = max(b[1] for b in bars)

    tb_ = TimingBuilder()
    delay = 0
    bar_shapes = []
    for i, (label, val, color) in enumerate(bars):
        y = top0 + i * (bar_h + gap)
        add_textbox(s, label, 0.7, y, track_x - 0.85, bar_h, 13, C.INK,
                    anchor=MSO_ANCHOR.MIDDLE, name=f"CatLabel_{i}")
        w = track_w_max * (val / max_val)
        bar = add_rect(s, track_x, y, w, bar_h, color, name=f"Bar_{i}")
        val_lbl = add_textbox(s, f"{val:.3f}", track_x + w + 0.15, y, 1.0, bar_h, 13, C.INK,
                               bold=True, anchor=MSO_ANCHOR.MIDDLE, name=f"Value_{i}")
        bar_shapes.append((bar, val_lbl))

    # reveal strongest (bottom row, last in list) to weakest (top row, first in list):
    # storyboard reveal order is strongest->weakest top-to-bottom; our strongest bar is
    # the LAST list entry (largest value, drawn at the bottom of the chart). Reveal
    # bottom-to-top so the strongest bar (which is also the flagged one) lands last.
    for bar, val_lbl in reversed(bar_shapes):
        tb_.add(bar, "wipe-right", delay, 350)
        tb_.add(val_lbl, "fade", delay + 200, 300)
        delay += 200

    caption = add_textbox(s, d["caption"], 0.7, 6.55, 10.5, 0.4, 13, C.TEXT_DIM, name="Caption")
    tb_.add(caption, "fade", delay + 200, 400)
    tb_.apply(s)
    set_transition(s, d["transition"])
    return s


# ---------------------------------------------------------------------------
# SLIDE 4 -- Aspect sentiment (Morph pair)
# ---------------------------------------------------------------------------
def build_slide4(prs):
    d = C.SLIDE_4
    bars = d["bars"]
    track_x = 3.1
    track_w_max = 8.6
    bar_h = 0.42
    gap = 0.13
    top0 = 2.35
    max_val = 100

    def make(state):
        s = blank_slide(prs)
        set_bg_white(s)
        add_kicker(s, d["kicker"])
        add_title(s, d["title"])
        add_source(s, d["source"])
        for i, (label, val, color) in enumerate(bars):
            y = top0 + i * (bar_h + gap)
            add_textbox(s, label, 0.7, y, track_x - 0.85, bar_h, 13, C.INK,
                        anchor=MSO_ANCHOR.MIDDLE, name=f"CatLabel_{label}")
            w = track_w_max * (val / max_val)
            bar_color = C.NEUTRAL_GREY if state == "a" else color
            add_rect(s, track_x, y, w, bar_h, bar_color, name=f"Bar_{label}")
            if state == "b":
                add_textbox(s, f"{val:.1f}", track_x + w + 0.12, y, 0.9, bar_h, 12, C.INK,
                            bold=True, anchor=MSO_ANCHOR.MIDDLE, name=f"Value_{label}")
        if state == "b":
            last_y = top0 + (len(bars) - 1) * (bar_h + gap)
            add_line(s, track_x + 0.02, last_y - 0.06, track_x + 0.02, last_y - 0.85, C.TEXT_FAINT,
                     width_pt=1.0, dash="dash", name="GapLine")
            add_textbox(s, d["caption"], 0.7, 6.35, 10.8, 0.35, 13, C.TEXT_DIM, name="Caption")
        return s

    sa = make("a")
    sb = make("b")
    set_transition(sa, "fade")
    set_transition(sb, "morph")
    return sa, sb


# ---------------------------------------------------------------------------
# SLIDE 5 -- High-risk share (single slide, Wipe, deliberately Fade-in from Slide 4)
# ---------------------------------------------------------------------------
def build_slide5(prs):
    d = C.SLIDE_5
    s = blank_slide(prs)
    set_bg_white(s)
    add_kicker(s, d["kicker"])
    add_title(s, d["title"])
    add_source(s, d["source"])

    bars = d["bars"]
    track_x = 3.1
    track_w_max = 8.6
    bar_h = 0.42
    gap = 0.13
    top0 = 2.35
    max_val = max(b[1] for b in bars) * 1.15

    tb_ = TimingBuilder()
    delay = 0
    grey_bars, highlight_bars = [], []
    for i, (label, val, color) in enumerate(bars):
        y = top0 + i * (bar_h + gap)
        add_textbox(s, label, 0.7, y, track_x - 0.85, bar_h, 13, C.INK,
                    anchor=MSO_ANCHOR.MIDDLE, name=f"CatLabel_{label}")
        w = track_w_max * (val / max_val)
        bar = add_rect(s, track_x, y, w, bar_h, color, name=f"Bar_{label}")
        vlbl = add_textbox(s, f"{val:.0f}%", track_x + w + 0.12, y, 0.8, bar_h, 12, C.INK,
                            bold=True, anchor=MSO_ANCHOR.MIDDLE, name=f"Value_{label}")
        if color == C.NEUTRAL_GREY:
            grey_bars.append((bar, vlbl))
        else:
            highlight_bars.append((bar, vlbl))

    for bar, vlbl in grey_bars:
        tb_.add(bar, "wipe-right", delay, 350)
        tb_.add(vlbl, "fade", delay + 200, 250)
        delay += 150
    delay += 150
    for bar, vlbl in highlight_bars:
        tb_.add(bar, "wipe-right", delay, 350)
        tb_.add(vlbl, "fade", delay + 200, 250)
        delay += 200

    caption = add_textbox(s, d["caption"], 0.7, 6.35, 10.8, 0.35, 13, C.TEXT_DIM, name="Caption")
    tb_.add(caption, "fade", delay + 250, 400)
    tb_.apply(s)
    set_transition(s, d["transition"])
    return s


# ---------------------------------------------------------------------------
# SLIDE 6 -- LHI version agreement (single slide, Wipe)
# ---------------------------------------------------------------------------
def build_slide6(prs):
    d = C.SLIDE_6
    s = blank_slide(prs)
    set_bg_white(s)
    add_kicker(s, d["kicker"])
    add_title(s, d["title"])
    add_source(s, d["source"])

    big = add_textbox(s, d["big_number"], 0.7, 3.0, 2.8, 1.4, 78, C.INK, bold=True,
                       font=C.FONT_DISPLAY, align=PP_ALIGN.LEFT, name="BigNumber")
    sub = add_textbox(s, d["big_number_sub"], 0.7, 4.45, 2.9, 0.9, 13, C.TEXT_DIM,
                       name="BigNumberSub")

    track_x = 6.3
    track_w_max = 5.3
    bar_h = 0.62
    gap = 0.42
    top0 = 2.55
    tb_ = TimingBuilder()
    tb_.add(big, "fade", 0, 500)
    tb_.add(sub, "fade", 250, 400)
    delay = 500
    for i, (label, pct, color) in enumerate(d["bars"]):
        y = top0 + i * (bar_h + gap)
        lbl = add_textbox(s, label, track_x - 2.1, y, 1.95, bar_h, 13, C.TEXT_DIM,
                           anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.RIGHT, name=f"CatLabel_{i}")
        w = track_w_max * (pct / 100)
        bar = add_rect(s, track_x, y, w, bar_h, color, name=f"Bar_{i}")
        vlbl = add_textbox(s, f"{pct}%", track_x + w + 0.12, y, 0.8, bar_h, 13, C.INK, bold=True,
                            anchor=MSO_ANCHOR.MIDDLE, name=f"Value_{i}")
        tb_.add(bar, "wipe-right", delay, 400)
        tb_.add(vlbl, "fade", delay + 250, 250)
        delay += 300
    tb_.apply(s)
    set_transition(s, d["transition"])
    return s


# ---------------------------------------------------------------------------
# SLIDE 7 -- Early warning (single slide, Fade)
# ---------------------------------------------------------------------------
def build_slide7(prs):
    d = C.SLIDE_7
    s = blank_slide(prs)
    set_bg_white(s)
    kicker = add_kicker(s, d["kicker"])
    title = add_title(s, d["title"])
    add_source(s, d["source"])

    big = add_textbox(s, d["big_number"], 0.7, 2.55, 11.9, 2.1, 130, d["big_number_color"],
                       bold=True, font=C.FONT_DISPLAY, align=PP_ALIGN.CENTER,
                       anchor=MSO_ANCHOR.MIDDLE, name="BigNumber")
    sub = add_textbox(s, d["big_number_sub"], 1.7, 4.75, 9.9, 0.9, 16, C.TEXT_DIM,
                       align=PP_ALIGN.CENTER, name="BigNumberSub")

    tb_ = TimingBuilder()
    tb_.add(kicker, "fade", 0, 350)
    tb_.add(title, "fade", 150, 450)
    tb_.add(big, "fade", 650, 550)
    tb_.add(sub, "fade", 1250, 400)
    tb_.apply(s)
    set_transition(s, d["transition"])
    return s


# ---------------------------------------------------------------------------
# SLIDE 8 -- Intervention priority (hybrid: frozen image + native overlay)
# ---------------------------------------------------------------------------
def build_slide8(prs):
    d = C.SLIDE_8
    s = blank_slide(prs)
    set_bg_white(s)

    img_path = ROOT / d["image_path"]
    aspect = d["image_w_px"] / d["image_h_px"]
    img_h = 5.95
    img_w = img_h * aspect
    img_x = (C.SLIDE_W_IN - img_w) / 2
    img_y = 0.45
    pic = s.shapes.add_picture(str(img_path), Inches(img_x), Inches(img_y), Inches(img_w), Inches(img_h))
    pic.name = "Fig11Image"

    # spotlight positions over the two annotated examples already in the (frozen,
    # unmodified) image -- centred on the arrow tips, fractions read off the source
    # PNG by cropping and visually inspecting chart_pack/shared/fig_11_..._final.png.
    sw1, sh1 = 0.5, 0.32
    spot1 = add_rect(s, img_x + img_w * 0.64 - sw1 / 2, img_y + img_h * 0.234 - sh1 / 2, sw1, sh1,
                      C.ACCENT, name="Spot1")
    spot1.fill.background()
    spot1.line.color.rgb = rgb(C.ACCENT)
    spot1.line.width = Pt(2.0)
    spot1.shadow.inherit = False

    sw2, sh2 = 0.5, 0.32
    spot2 = add_rect(s, img_x + img_w * 0.57 - sw2 / 2, img_y + img_h * 0.78 - sh2 / 2, sw2, sh2,
                      C.RISK_COLORS["Watch"], name="Spot2")
    spot2.fill.background()
    spot2.line.color.rgb = rgb(C.RISK_COLORS["Watch"])
    spot2.line.width = Pt(2.0)
    spot2.shadow.inherit = False

    caption = add_textbox(s, d["caption_native"], 0.7, img_y + img_h + 0.12, 11.9, 0.4, 14,
                           C.INK, bold=True, font=C.FONT_DISPLAY, name="ClosingCaption")
    add_source(s, d["source"])

    tb_ = TimingBuilder()
    tb_.add(pic, "fade", 0, 600)
    tb_.add(spot1, "wipe-right", 700, 350)
    tb_.add(spot2, "wipe-right", 1050, 350)
    tb_.add(caption, "fade", 1500, 400)
    tb_.apply(s)
    set_transition(s, d["transition"])
    return s


def main():
    prs = new_deck()
    build_slide1(prs)
    build_slide2(prs)
    build_slide3(prs)
    build_slide4(prs)
    build_slide5(prs)
    build_slide6(prs)
    build_slide7(prs)
    build_slide8(prs)
    out_path = OUT_DIR / "QSR_LHI_Executive_Presentation.pptx"
    prs.save(str(out_path))
    print("wrote", out_path, "-", len(prs.slides._sldIdLst), "slides")
    return out_path


if __name__ == "__main__":
    main()
