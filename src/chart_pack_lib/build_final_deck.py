"""
Builds the final 11-slide static executive presentation (visual refinement pass).
No animation, no morph, no transitions. Every chart is the actual released PNG from
chart_pack/ -- never recreated, never modified. Native shapes are used only for text,
the process diagram, stat callouts, and the priority-logic diagram (all
presentation-layer content, not analytical charts).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from PIL import Image

import final_deck_content as C

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "chart_pack" / "final_deck"
OUT_DIR.mkdir(exist_ok=True)

LEFT = 0.7
RIGHT_MARGIN = 0.7
CONTENT_W = C.SLIDE_W_IN - LEFT - RIGHT_MARGIN  # 11.933
FOOTER_Y = 7.08


def rgb(hexstr):
    return RGBColor.from_string(hexstr)


def new_deck():
    prs = Presentation()
    prs.slide_width = Inches(C.SLIDE_W_IN)
    prs.slide_height = Inches(C.SLIDE_H_IN)
    return prs


def blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def set_bg(slide, hexcolor):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb(hexcolor)


def add_textbox(slide, text, left, top, width, height, size, color, bold=False,
                 italic=False, font=C.FONT_BODY, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
                 line_spacing=1.12):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
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


def add_rect(slide, left, top, width, height, hexcolor, radius=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    r = slide.shapes.add_shape(shape_type, Inches(left), Inches(top), Inches(width), Inches(height))
    r.fill.solid()
    r.fill.fore_color.rgb = rgb(hexcolor)
    r.line.fill.background()
    r.shadow.inherit = False
    return r


def add_line(slide, x1, y1, x2, y2, hexcolor, width_pt=1.0, dash=None):
    ln = slide.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    ln.line.color.rgb = rgb(hexcolor)
    ln.line.width = Pt(width_pt)
    if dash:
        from pptx.oxml.ns import qn
        lnEl = ln.line._get_or_add_ln()
        d = lnEl.makeelement(qn("a:prstDash"), {"val": dash})
        lnEl.append(d)
    return ln


def add_kicker(slide, text, color=C.ACCENT, x=LEFT, y=0.42):
    return add_textbox(slide, text, x, y, 9.0, 0.3, 11, color, bold=True, font=C.FONT_BODY)


def add_title(slide, text, x=LEFT, y=0.74, width=None, size=None):
    if width is None:
        width = CONTENT_W
    if size is None:
        size = 22 if len(text) > 78 else (25 if len(text) > 55 else 29)
    return add_textbox(slide, text, x, y, width, 1.0, size, C.INK, bold=True,
                        font=C.FONT_DISPLAY, line_spacing=1.08)


def add_footer(slide, text):
    return add_textbox(slide, text, LEFT, FOOTER_Y, CONTENT_W - 0.6, 0.35, 9.5, C.TEXT_FAINT,
                        italic=True)


def add_page_num(slide, n):
    return add_textbox(slide, f"{n:02d}", C.SLIDE_W_IN - 0.85, FOOTER_Y, 0.5, 0.3, 9.5,
                        C.TEXT_FAINT, align=PP_ALIGN.RIGHT)


def place_image(slide, path, left, top, max_w, max_h, valign="top"):
    im = Image.open(ROOT / path)
    aspect = im.size[0] / im.size[1]
    w, h = max_w, max_w / aspect
    if h > max_h:
        h = max_h
        w = max_h * aspect
    x = left + (max_w - w) / 2
    y = top if valign == "top" else top + (max_h - h) / 2
    slide.shapes.add_picture(str(ROOT / path), Inches(x), Inches(y), Inches(w), Inches(h))
    return x, y, w, h


# ---------------------------------------------------------------------------
def build_title(prs, d, n):
    s = blank_slide(prs)
    set_bg(s, C.INK)
    add_textbox(s, d["kicker"], LEFT, 2.15, 10.0, 0.3, 12, "8FC4CF", bold=True)
    add_textbox(s, d["title"], LEFT, 2.55, 11.5, 1.3, 46, C.WHITE, bold=True, font=C.FONT_DISPLAY)
    add_textbox(s, d["subtitle"], LEFT, 3.95, 10.6, 0.9, 18, "C3C9D2", font=C.FONT_DISPLAY,
                line_spacing=1.25)
    x0 = LEFT
    card_w = (CONTENT_W - 0.9) / 4
    gap = 0.3
    y0 = 5.15
    for i, (num, label) in enumerate(d["stats"]):
        x = x0 + i * (card_w + gap)
        add_textbox(s, num, x, y0, card_w, 0.65, 34, "8FC4CF", bold=True, font=C.FONT_DISPLAY)
        add_textbox(s, label, x, y0 + 0.68, card_w, 0.6, 11.5, "A9B2BD")
    add_textbox(s, d["footer"], LEFT, 7.0, CONTENT_W, 0.4, 10, "7C8794", italic=True)
    return s


def build_questions_slide(prs, d, n):
    """Slide 2 -- shortened, four prominent question rows, no intro paragraph."""
    s = blank_slide(prs)
    set_bg(s, C.WHITE)
    add_kicker(s, d["kicker"])
    add_title(s, d["title"], size=27)
    items = d["list_items"]
    y = 2.35
    row_h = 1.08
    for q, a in items:
        add_rect(s, LEFT, y + 0.03, 0.06, 0.66, C.ACCENT)
        add_textbox(s, q, LEFT + 0.32, y, CONTENT_W - 0.32, 0.42, 21, C.INK, bold=True,
                    font=C.FONT_DISPLAY)
        add_textbox(s, a, LEFT + 0.32, y + 0.46, CONTENT_W - 0.32, 0.5, 14.5, C.TEXT_DIM,
                    line_spacing=1.2)
        y += row_h
    add_footer(s, d["footer"])
    add_page_num(s, n)
    return s


def build_process4_slide(prs, d, n):
    """Slide 3 -- 4 phase bands, 13 stages subordinate (small chips) under each."""
    s = blank_slide(prs)
    set_bg(s, C.WHITE)
    add_kicker(s, d["kicker"])
    add_title(s, d["title"], size=21)
    phases = d["phases"]
    n_phases = len(phases)
    gap = 0.28
    col_w = (CONTENT_W - gap * (n_phases - 1)) / n_phases
    top = 2.15
    head_h = 0.95
    for i, (num, label, stages) in enumerate(phases):
        x = LEFT + i * (col_w + gap)
        add_rect(s, x, top, col_w, head_h, C.ACCENT_SOFT, radius=True)
        add_textbox(s, num, x + 0.16, top + 0.1, 0.5, 0.4, 20, C.ACCENT, bold=True,
                    font=C.FONT_DISPLAY)
        add_textbox(s, label, x + 0.16, top + 0.48, col_w - 0.32, 0.45, 13.5, C.INK, bold=True,
                    font=C.FONT_DISPLAY, line_spacing=1.05)
        chip_y = top + head_h + 0.18
        for stage in stages:
            add_textbox(s, "-  " + stage, x + 0.05, chip_y, col_w - 0.1, 0.32, 11.5, C.TEXT_DIM)
            chip_y += 0.36
        if i < n_phases - 1:
            arrow_x = x + col_w + gap / 2
            add_textbox(s, ">", arrow_x - 0.12, top + head_h / 2 - 0.18, 0.24, 0.36, 16,
                        C.TEXT_FAINT, bold=True, align=PP_ALIGN.CENTER)
    add_textbox(s, d["body"], LEFT, 5.85, CONTENT_W, 0.75, 14.5, C.TEXT_DIM, line_spacing=1.25)
    add_footer(s, d["footer"])
    add_page_num(s, n)
    return s


def build_eda_hero_slide(prs, d, n):
    """Slide 4 -- chart dominant, two big-number callouts below, one short line."""
    s = blank_slide(prs)
    set_bg(s, C.WHITE)
    add_kicker(s, d["kicker"])
    add_title(s, d["title"])
    img_top = 1.85
    img_h = 4.15
    place_image(s, d["images"][0], LEFT, img_top, CONTENT_W * 0.82, img_h)
    stat_x = LEFT + CONTENT_W * 0.84
    stat_w = CONTENT_W * 0.16
    sy = img_top + 0.4
    for num, label in d["stats"]:
        add_textbox(s, num, stat_x, sy, stat_w, 0.55, 32, C.ACCENT, bold=True, font=C.FONT_DISPLAY)
        add_textbox(s, label, stat_x, sy + 0.58, stat_w, 0.75, 11.5, C.TEXT_DIM, line_spacing=1.15)
        sy += 1.65
    add_textbox(s, d["body"], LEFT, img_top + img_h + 0.15, CONTENT_W, 0.55, 13.5, C.TEXT_DIM,
                line_spacing=1.2)
    add_footer(s, d["footer"])
    add_page_num(s, n)
    return s


def build_hero_secondary_slide(prs, d, n):
    """Slide 5 -- LEAKY vs SAFE as large hero (left, ~62%), SHAP as smaller secondary (right)."""
    s = blank_slide(prs)
    set_bg(s, C.WHITE)
    add_kicker(s, d["kicker"])
    add_title(s, d["title"], size=21)
    hero_w = CONTENT_W * 0.60
    sec_w = CONTENT_W - hero_w - 0.4
    img_top = 2.1
    img_h = 4.15
    place_image(s, d["hero_image"], LEFT, img_top, hero_w, img_h)
    sx = LEFT + hero_w + 0.4
    add_textbox(s, d["secondary_label"], sx, img_top, sec_w, 0.55, 12, C.TEXT_FAINT, italic=True,
                line_spacing=1.15)
    place_image(s, d["secondary_image"], sx, img_top + 0.6, sec_w, img_h - 0.6)
    add_textbox(s, d["takeaway"], LEFT, img_top + img_h + 0.18, CONTENT_W, 0.55, 14, C.INK,
                bold=True, font=C.FONT_DISPLAY, line_spacing=1.2)
    add_footer(s, d["footer"])
    add_page_num(s, n)
    return s


def build_chart_slide(prs, d, n):
    s = blank_slide(prs)
    set_bg(s, C.WHITE)
    add_kicker(s, d["kicker"])
    # Only render a native title when it differs from the chart image's own baked
    # title (avoids duplicate text on screen when they already match).
    if d.get("show_title", False):
        add_title(s, d["title"], size=21)
        img_top = 2.15
        img_h = 4.15
    else:
        img_top = 1.75
        img_h = 4.55
    place_image(s, d["images"][0], LEFT, img_top, CONTENT_W, img_h)
    add_textbox(s, d["body"], LEFT, img_top + img_h + 0.15, CONTENT_W, 0.7, 13.5, C.TEXT_DIM,
                line_spacing=1.25)
    add_footer(s, d["footer"])
    add_page_num(s, n)
    return s


def build_priority_slide(prs, d, n):
    """Slide 8 -- native Health x Trajectory x Confidence -> Priority logic strip above the chart."""
    s = blank_slide(prs)
    set_bg(s, C.WHITE)
    add_kicker(s, d["kicker"])
    # No native title here -- the chart image below already carries this exact
    # headline; a second copy would be the same duplicate-text problem fixed on
    # slides 06/07. The logic strip reads fine standing alone under the kicker.
    logic = d["logic"]
    top = 1.15
    box_h = 0.55
    box_w = 1.9
    gap_sym_w = 0.4
    n_boxes = len(logic)
    result_w = 2.3
    total_w = box_w * n_boxes + gap_sym_w * n_boxes + result_w
    x0 = LEFT + (CONTENT_W - total_w) / 2
    x = x0
    for i, term in enumerate(logic):
        add_rect(s, x, top, box_w, box_h, C.ACCENT_SOFT, radius=True)
        add_textbox(s, term, x, top, box_w, box_h, 13.5, C.ACCENT, bold=True, font=C.FONT_DISPLAY,
                    align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        x += box_w
        add_textbox(s, "x", x, top, gap_sym_w, box_h, 16, C.TEXT_FAINT, bold=True,
                    align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        x += gap_sym_w
    add_textbox(s, ">", x, top, 0.3, box_h, 16, C.TEXT_FAINT, bold=True,
                align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    x += 0.3
    add_rect(s, x, top, result_w - 0.3, box_h, C.INK, radius=True)
    add_textbox(s, d["logic_result"], x, top, result_w - 0.3, box_h, 13.5, C.WHITE, bold=True,
                font=C.FONT_DISPLAY, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    img_top = top + box_h + 0.3
    img_h = 4.5
    place_image(s, d["images"][0], LEFT, img_top, CONTENT_W, img_h)
    add_textbox(s, d["body"], LEFT, img_top + img_h + 0.1, CONTENT_W, 0.42, 12.5, C.TEXT_DIM,
                line_spacing=1.18)
    add_footer(s, d["footer"])
    add_page_num(s, n)
    return s


def build_themes_slide(prs, d, n):
    """Slide 9 -- 3 themed columns instead of 5 equal-weight cards."""
    s = blank_slide(prs)
    set_bg(s, C.WHITE)
    add_kicker(s, d["kicker"])
    add_title(s, d["title"], size=25)
    themes = d["themes"]
    n_themes = len(themes)
    gap = 0.4
    col_w = (CONTENT_W - gap * (n_themes - 1)) / n_themes
    top = 2.3
    for i, (theme_name, points) in enumerate(themes):
        x = LEFT + i * (col_w + gap)
        add_rect(s, x, top, 0.5, 0.5, C.ACCENT_SOFT, radius=True)
        add_textbox(s, str(i + 1), x, top, 0.5, 0.5, 18, C.ACCENT, bold=True, font=C.FONT_DISPLAY,
                    align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        add_textbox(s, theme_name, x, top + 0.65, col_w, 0.75, 17.5, C.INK, bold=True,
                    font=C.FONT_DISPLAY, line_spacing=1.1)
        py = top + 1.5
        for pt in points:
            add_rect(s, x, py + 0.07, 0.08, 0.08, C.ACCENT, radius=True)
            add_textbox(s, pt, x + 0.24, py, col_w - 0.24, 1.0, 12.5, C.TEXT_DIM, line_spacing=1.25)
            py += 1.15
    add_footer(s, d["footer"])
    add_page_num(s, n)
    return s


def build_conclusion3_slide(prs, d, n):
    """Slide 10 -- big number hero (left), 3 short takeaway lines (right), no paragraph."""
    s = blank_slide(prs)
    set_bg(s, C.WHITE)
    add_kicker(s, d["kicker"])
    # No native title -- the chart image already carries this exact headline as its
    # own baked-in caption; restating it here would be the same duplicate-text issue
    # fixed on slides 06/07/08.
    img_top = 1.3
    img_w = CONTENT_W * 0.52
    img_h = 5.15
    place_image(s, d["images"][0], LEFT, img_top, img_w, img_h, valign="middle")
    tx = LEFT + img_w + 0.5
    tw = CONTENT_W - img_w - 0.5
    ty = img_top + 0.55
    for i, line in enumerate(d["takeaways"]):
        add_rect(s, tx, ty + 0.06, 0.08, 0.08, C.ACCENT, radius=True)
        add_textbox(s, line, tx + 0.26, ty, tw - 0.26, 1.1, 15, C.INK, line_spacing=1.3)
        ty += 1.35
    add_footer(s, d["footer"])
    add_page_num(s, n)
    return s


def build_outlet_compare_slide(prs, d, n):
    """Two real, named locations side by side -- one struggling, one healthy --
    each broken down into the same four pillars, so the scoring logic is shown
    working on concrete cases rather than only in aggregate."""
    s = blank_slide(prs)
    set_bg(s, C.WHITE)
    add_kicker(s, d["kicker"])
    add_title(s, d["title"], size=21)

    top = 1.85
    gap = 0.4
    card_w = (CONTENT_W - gap) / 2
    card_h = 4.5

    for i, card in enumerate(d["cards"]):
        x = LEFT + i * (card_w + gap)
        add_rect(s, x, top, card_w, card_h, "F7F6F3", radius=True)
        ac = card["accent"]
        pad = 0.28
        cy = top + 0.2

        # status pill
        pill_w = 1.5
        add_rect(s, x + pad, cy, pill_w, 0.3, ac, radius=True)
        add_textbox(s, card["label"], x + pad, cy, pill_w, 0.3, 10.5, C.WHITE, bold=True,
                    align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        cy += 0.46

        add_textbox(s, card["name"], x + pad, cy, card_w - 2 * pad, 0.36, 17, C.INK, bold=True,
                    font=C.FONT_DISPLAY)
        cy += 0.36
        add_textbox(s, card["place"], x + pad, cy, card_w - 2 * pad, 0.28, 11, C.TEXT_FAINT)
        cy += 0.4

        add_textbox(s, card["lhi"], x + pad, cy, 1.3, 0.55, 32, ac, bold=True, font=C.FONT_DISPLAY)
        add_textbox(s, card["risk_line"], x + pad + 1.35, cy + 0.06, card_w - 2 * pad - 1.35, 0.5,
                    12, C.INK, bold=True, line_spacing=1.1)
        cy += 0.62

        add_textbox(s, card["trend"], x + pad, cy, card_w - 2 * pad, 0.28, 12, C.TEXT_DIM)
        cy += 0.27
        add_textbox(s, card["peer"], x + pad, cy, card_w - 2 * pad, 0.28, 11, C.TEXT_FAINT)
        cy += 0.38

        bar_track_w = card_w - 2 * pad - 1.55
        for label, val in card["pillars"]:
            add_textbox(s, label, x + pad, cy, 1.3, 0.24, 10.5, C.TEXT_DIM)
            add_rect(s, x + pad + 1.35, cy + 0.03, bar_track_w, 0.15, C.BORDER)
            fill_w = max(bar_track_w * val / 100.0, 0.04)
            add_rect(s, x + pad + 1.35, cy + 0.03, fill_w, 0.15, ac)
            add_textbox(s, str(int(round(val))), x + pad + 1.35 + bar_track_w + 0.08, cy - 0.03,
                        0.4, 0.24, 10.5, C.INK, bold=True)
            cy += 0.29
        cy += 0.06

        add_textbox(s, card["note"], x + pad, cy, card_w - 2 * pad, 0.55, 10.5, C.TEXT_DIM,
                    italic=True, line_spacing=1.2)

    add_textbox(s, d["body"], LEFT, top + card_h + 0.2, CONTENT_W, 0.5, 13, C.TEXT_DIM,
                line_spacing=1.2)
    add_footer(s, d["footer"])
    add_page_num(s, n)
    return s


def build_weights_slide(prs, d, n):
    """Four pillar weights with a one-line business rationale each -- the direct
    answer to 'why does each component count for what it counts for'."""
    s = blank_slide(prs)
    set_bg(s, C.WHITE)
    add_kicker(s, d["kicker"])
    add_title(s, d["title"], size=21)

    pillars = d["pillars"]
    n_p = len(pillars)
    gap = 0.35
    col_w = (CONTENT_W - gap * (n_p - 1)) / n_p
    top = 2.15

    for i, (name, weight, rationale) in enumerate(pillars):
        x = LEFT + i * (col_w + gap)
        add_rect(s, x, top, col_w, 3.85, "F7F6F3", radius=True)
        add_textbox(s, weight, x + 0.22, top + 0.26, col_w - 0.44, 0.75, 32, C.ACCENT, bold=True,
                    font=C.FONT_DISPLAY)
        add_textbox(s, name, x + 0.22, top + 1.02, col_w - 0.44, 0.6, 14.5, C.INK, bold=True,
                    font=C.FONT_DISPLAY, line_spacing=1.1)
        add_textbox(s, rationale, x + 0.22, top + 1.65, col_w - 0.44, 2.1, 11.5, C.TEXT_DIM,
                    line_spacing=1.3)

    add_textbox(s, d["body"], LEFT, top + 3.85 + 0.25, CONTENT_W, 0.7, 13, C.TEXT_DIM,
                line_spacing=1.25)
    add_footer(s, d["footer"])
    add_page_num(s, n)
    return s


def build_closing_slide(prs, d, n):
    s = blank_slide(prs)
    set_bg(s, C.INK)
    add_textbox(s, d["title"], LEFT, 3.05, 11.5, 1.1, 48, C.WHITE, bold=True, font=C.FONT_DISPLAY)
    add_textbox(s, d["subtitle"], LEFT, 4.15, 10.6, 0.6, 18, "A9B2BD", font=C.FONT_DISPLAY)
    add_textbox(s, d["footer"], LEFT, 6.85, CONTENT_W, 0.4, 11, "7C8794", italic=True)
    return s


BUILDERS = {
    "title": build_title,
    "questions": build_questions_slide,
    "process4": build_process4_slide,
    "eda_hero": build_eda_hero_slide,
    "hero_secondary": build_hero_secondary_slide,
    "chart": build_chart_slide,
    "priority": build_priority_slide,
    "themes": build_themes_slide,
    "conclusion3": build_conclusion3_slide,
    "closing": build_closing_slide,
    "outlet_compare": build_outlet_compare_slide,
    "weights": build_weights_slide,
}


def main():
    prs = new_deck()
    for i, d in enumerate(C.SLIDES, 1):
        BUILDERS[d["kind"]](prs, d, i)
    out_path = OUT_DIR / "QSR_LHI_Executive_Presentation_Final.pptx"
    prs.save(str(out_path))
    print("wrote", out_path, "-", len(C.SLIDES), "slides")
    return out_path


if __name__ == "__main__":
    main()
