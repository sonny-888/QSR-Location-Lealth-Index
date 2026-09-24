"""
Renders a static contact sheet from the ACTUAL saved final-deck .pptx -- reads real
shape geometry/fill/text/pictures straight out of the OOXML via python-pptx, so this
is a faithful proxy for each slide as it will actually look (no animation involved,
so there is nothing transient to miss this time).
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN

sys.path.insert(0, str(Path(__file__).parent))
import final_deck_content as C  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "chart_pack" / "final_deck" / "QSR_LHI_Executive_Presentation_Final.pptx"
OUT = ROOT / "chart_pack" / "final_deck" / "contact_sheet.png"

DPI = 110
FONT_DIR = Path(r"C:\Windows\Fonts")
_font_cache = {}


def get_font(name, size, bold=False, italic=False):
    key = (name, size, bold, italic)
    if key in _font_cache:
        return _font_cache[key]
    size_px = max(6, int(size * DPI / 72))
    if name == "Cambria":
        candidates = ["cambriab.ttf"] if bold else ["cambria.ttc"]
    else:
        if bold and italic:
            candidates = ["calibriz.ttf"]
        elif bold:
            candidates = ["calibrib.ttf"]
        elif italic:
            candidates = ["calibrii.ttf"]
        else:
            candidates = ["calibri.ttf"]
    font = None
    for c in candidates:
        p = FONT_DIR / c
        if p.exists():
            try:
                font = ImageFont.truetype(str(p), size_px)
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def emu_to_px(v):
    return int(v / 914400 * DPI)


def get_bg_color(slide):
    try:
        fill = slide.background.fill
        if fill.type == 1:
            return "#" + str(fill.fore_color.rgb)
    except Exception:
        pass
    return "#FFFFFF"


def draw_slide(slide, sw_px, sh_px):
    bg = get_bg_color(slide)
    img = Image.new("RGB", (sw_px, sh_px), bg)
    draw = ImageDraw.Draw(img)
    for shape in slide.shapes:
        try:
            l, t, w, h = shape.left, shape.top, shape.width, shape.height
        except TypeError:
            continue
        if l is None:
            continue
        x0, y0 = emu_to_px(l), emu_to_px(t)
        x1, y1 = emu_to_px(l + (w or 0)), emu_to_px(t + (h or 0))

        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            try:
                blob = shape.image.blob
                import io
                pic = Image.open(io.BytesIO(blob)).convert("RGB")
                pic = pic.resize((max(1, x1 - x0), max(1, y1 - y0)))
                img.paste(pic, (x0, y0))
            except Exception:
                pass
            continue

        if hasattr(shape, "line") and not getattr(shape, "has_text_frame", False) and \
                shape.shape_type not in (MSO_SHAPE_TYPE.AUTO_SHAPE,):
            try:
                color = shape.line.color.rgb
                draw.line([(x0, y0), (x1, y1)], fill=str(color), width=2)
                continue
            except Exception:
                pass

        try:
            fill_color = None
            if shape.fill.type is not None and shape.fill.type == 1:
                fill_color = "#" + str(shape.fill.fore_color.rgb)
            if fill_color:
                radius = 8 if "ROUND" in str(getattr(shape, "adjustments", "")) else 0
                try:
                    is_round = shape.auto_shape_type is not None and "ROUND" in str(shape.auto_shape_type)
                except Exception:
                    is_round = False
                if is_round:
                    draw.rounded_rectangle([x0, y0, max(x0, x1), max(y0, y1)], radius=10, fill=fill_color)
                else:
                    draw.rectangle([x0, y0, max(x0, x1), max(y0, y1)], fill=fill_color)
        except Exception:
            pass

        if getattr(shape, "has_text_frame", False):
            tf = shape.text_frame
            box_w = max(1, x1 - x0)
            line_specs = []
            for p in tf.paragraphs:
                for r in p.runs:
                    if not r.text:
                        continue
                    sz = r.font.size.pt if r.font.size else 12
                    fnt = get_font(r.font.name or "Calibri", sz, bool(r.font.bold), bool(r.font.italic))
                    col = "#" + str(r.font.color.rgb) if r.font.color and r.font.color.type is not None else "#141F28"
                    for wrapped in _wrap_text(draw, r.text, fnt, box_w):
                        line_specs.append((wrapped, fnt, col, p.alignment, sz))
            total_text_h = sum(int(sz * 1.22 * DPI / 72) for _, _, _, _, sz in line_specs)
            y_cursor = y0
            anchor = str(tf.vertical_anchor) if tf.vertical_anchor is not None else ""
            if "MIDDLE" in anchor:
                y_cursor = y0 + max(0, ((y1 - y0) - total_text_h) // 2)
            for text, fnt, col, align, sz in line_specs:
                bbox = draw.textbbox((0, 0), text, font=fnt)
                tw = bbox[2] - bbox[0]
                if align == PP_ALIGN.CENTER:
                    tx = x0 + max(0, ((x1 - x0) - tw) // 2)
                elif align == PP_ALIGN.RIGHT:
                    tx = x1 - tw
                else:
                    tx = x0
                draw.text((tx, y_cursor), text, font=fnt, fill=col)
                y_cursor += int(sz * 1.22 * DPI / 72)
    return img


def _wrap_text(draw, text, font, max_w_px):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        tw = draw.textbbox((0, 0), trial, font=font)[2]
        if tw <= max_w_px or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


NICE_NAME = {
    "title": "Title",
    "context": "Business context",
    "process": "Process",
    "eda": "EDA",
    "model_integrity": "Model integrity",
    "cx": "Customer experience",
    "outlet_compare": "Two real locations",
    "weights": "How weights were chosen",
    "lhi_construction": "LHI construction",
    "prioritisation": "Prioritisation",
    "recommendations": "Recommendations",
    "limitations": "Limitations",
    "conclusion": "Conclusion",
    "thankyou": "Thank you",
}


def main():
    prs = Presentation(str(DECK))
    sw_px = emu_to_px(prs.slide_width)
    sh_px = emu_to_px(prs.slide_height)
    slides = list(prs.slides)
    assert len(slides) == len(C.SLIDES), f"{len(slides)} slides in pptx vs {len(C.SLIDES)} in content model"
    labels = [f"{i+1:02d} {NICE_NAME.get(d['key'], d['key'])}" for i, d in enumerate(C.SLIDES)]

    panels = [draw_slide(s, sw_px, sh_px) for s in slides]

    scale = 0.34
    pw, ph = int(sw_px * scale), int(sh_px * scale)
    cols = 2
    rows = (len(slides) + cols - 1) // cols
    pad = 20
    label_h = 26
    sheet_w = cols * pw + (cols + 1) * pad
    sheet_h = rows * (ph + label_h) + (rows + 1) * pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#e7e4dd")
    d = ImageDraw.Draw(sheet)
    label_font = get_font("Calibri", 11, bold=True)
    for i, (panel, label) in enumerate(zip(panels, labels)):
        r, c = divmod(i, cols)
        x = pad + c * (pw + pad)
        y = pad + r * (ph + label_h + pad)
        thumb = panel.resize((pw, ph))
        d.rectangle([x - 2, y - 2, x + pw + 2, y + ph + 2], outline="#8b93a0", width=2)
        sheet.paste(thumb, (x, y))
        d.text((x, y + ph + 4), label, font=label_font, fill="#141F28")
    sheet.save(OUT)
    print("wrote", OUT, sheet.size)


if __name__ == "__main__":
    main()
