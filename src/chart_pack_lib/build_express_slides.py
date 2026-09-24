"""
Builds self-contained HTML for each of the 17 slides in QSR_LHI_Presentation.pptx,
using REAL geometry/color/font/text/chart-data extracted directly from the pptx
(chart_pack/_lib/deck_extract.json) -- nothing here is invented. Charts (native
PowerPoint graphicFrames) are rebuilt as simple CSS bar comparisons using their
real category/series values, since Adobe Express's HTML importer has no concept
of an embedded OOXML chart object.

Output: one HTML file per slide in chart_pack/_lib/express_html/slideNN.html
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "chart_pack" / "_lib" / "deck_extract.json").read_text(encoding="utf-8"))
OUT_DIR = ROOT / "chart_pack" / "_lib" / "express_html"
OUT_DIR.mkdir(exist_ok=True)

SCALE = 144  # px per inch (matches the validated pilot: 1920x1080 for 13.333x7.5in)
CW, CH = 1920, 1080

FONT_MAP = {
    "Cambria": "Georgia,'Times New Roman',serif",
    "Calibri": "Arial,Helvetica,sans-serif",
}

BAR_COLORS = ["#C9CDD3", "#F0A092", "#E8503A", "#1B222C", "#8B94A1"]
INK = "#1B222C"
TEXT_DIM = "#5B6470"
ACCENT = "#E8503A"


def px(inches):
    return round(inches * SCALE)


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace("–", "&ndash;").replace("—", "&mdash;")
             .replace("�", "&mdash;"))


def render_text_shape(sh):
    l, t, w, h = px(sh["left"]), px(sh["top"]), px(sh["width"]), px(sh["height"])
    paras_html = []
    for p in sh.get("paragraphs", []):
        align = "center" if "CENTER" in (p["align"] or "") else ("right" if "RIGHT" in (p["align"] or "") else "left")
        runs_html = []
        for r in p["runs"]:
            if not r["text"]:
                continue
            font = FONT_MAP.get(r["font"], "Arial,Helvetica,sans-serif")
            size = px((r["size_pt"] or 12) / 72)
            color = r["color"] or INK
            weight = 700 if r["bold"] else 400
            style_ = "italic" if r["italic"] else "normal"
            runs_html.append(
                f'<span style="font-family:{font};font-size:{size}px;color:{color};'
                f'font-weight:{weight};font-style:{style_};">{esc(r["text"])}</span>')
        if runs_html:
            paras_html.append(f'<div style="text-align:{align};margin:0;">{"".join(runs_html)}</div>')
    if not paras_html:
        return ""
    return (f'<div style="position:absolute;left:{l}px;top:{t}px;width:{w}px;height:{h}px;'
            f'line-height:1.18;">{"".join(paras_html)}</div>')


def render_auto_shape(sh):
    if "fill" not in sh:
        return ""
    l, t, w, h = px(sh["left"]), px(sh["top"]), px(sh["width"]), px(sh["height"])
    name = sh["name"]
    radius = "999px" if "Oval" in name else ("18px" if "Rounded" in name else "0")
    return f'<div style="position:absolute;left:{l}px;top:{t}px;width:{w}px;height:{h}px;background:{sh["fill"]};border-radius:{radius};"></div>'


def render_line(sh):
    l, t, w, h = px(sh["left"]), px(sh["top"]), px(sh["width"]), px(sh["height"])
    color = sh.get("line_color") or "#DADEE3"
    thick = max(1, round((sh.get("line_width_pt") or 1) * 2))
    if h <= 2:
        return f'<div style="position:absolute;left:{l}px;top:{t}px;width:{max(w,1)}px;height:{thick}px;background:{color};"></div>'
    else:
        return f'<div style="position:absolute;left:{l}px;top:{t}px;width:{thick}px;height:{max(h,1)}px;background:{color};"></div>'


def render_chart(sh):
    l, t, w, h = px(sh["left"]), px(sh["top"]), px(sh["width"]), px(sh["height"])
    cats = sh.get("chart_categories", [])
    series = sh.get("chart_series", [])
    if not cats or not series:
        return ""
    n_cats = len(cats)
    n_series = len(series)
    all_vals = [v for s in series for v in s["values"] if v is not None]
    max_val = max(all_vals) if all_vals else 1
    row_h = h / n_cats
    bar_group_h = row_h * 0.62
    bar_h = bar_group_h / n_series
    label_w = w * 0.30
    track_w = w - label_w - 90
    parts = [f'<div style="position:absolute;left:{l}px;top:{t}px;width:{w}px;height:{h}px;font-family:Arial,Helvetica,sans-serif;">']
    for ci, cat in enumerate(cats):
        row_top = round(ci * row_h + (row_h - bar_group_h) / 2)
        cat_label = str(cat).replace("\n", " ")
        parts.append(f'<div style="position:absolute;left:0px;top:{round(ci*row_h)}px;width:{round(label_w)}px;height:{round(row_h)}px;'
                      f'display:flex;align-items:center;font-size:15px;color:{TEXT_DIM};">{esc(cat_label)}</div>')
        for si, s in enumerate(series):
            val = s["values"][ci] if ci < len(s["values"]) else None
            if val is None:
                continue
            bw = max(2, round(track_w * (val / max_val))) if max_val else 2
            by = row_top + round(si * bar_h)
            color = BAR_COLORS[si % len(BAR_COLORS)]
            val_str = f"{val:.3f}" if abs(val) < 5 and val != int(val) else (f"{val:.0f}" if val == int(val) else f"{val:.1f}")
            parts.append(f'<div style="position:absolute;left:{round(label_w)}px;top:{by}px;width:{bw}px;height:{round(bar_h*0.82)}px;background:{color};border-radius:2px;"></div>')
            parts.append(f'<div style="position:absolute;left:{round(label_w)+bw+10}px;top:{by}px;width:80px;height:{round(bar_h*0.82)}px;'
                          f'display:flex;align-items:center;font-size:13px;font-weight:700;color:{INK};">{val_str}</div>')
    if n_series > 1:
        legend_y = h - 22
        lx = round(label_w)
        for si, s in enumerate(series):
            color = BAR_COLORS[si % len(BAR_COLORS)]
            parts.append(f'<div style="position:absolute;left:{lx}px;top:{legend_y}px;width:12px;height:12px;background:{color};border-radius:2px;"></div>')
            parts.append(f'<div style="position:absolute;left:{lx+16}px;top:{legend_y-3}px;font-size:12px;color:{TEXT_DIM};">{esc(s["name"] or "")}</div>')
            lx += 16 + len(s["name"] or "") * 7 + 24
    parts.append("</div>")
    return "".join(parts)


def build_slide_html(sdata):
    shapes = sdata["shapes"]
    bg = "#FFFFFF"
    body_parts = []
    for sh in shapes:
        if sh["left"] == 0 and sh["top"] == 0 and sh.get("width", 0) > 13 and sh.get("height", 0) > 7 and sh.get("fill"):
            bg = sh["fill"]
            continue
        t = sh["type"]
        if "CHART" in t:
            body_parts.append(render_chart(sh))
        elif "LINE" in t:
            body_parts.append(render_line(sh))
        elif "PICTURE" in t:
            l_, t_, w_, h_ = px(sh["left"]), px(sh["top"]), px(sh["width"]), px(sh["height"])
            body_parts.append(f'<div style="position:absolute;left:{l_}px;top:{t_}px;width:{w_}px;height:{h_}px;'
                               f'background:#E9ECEF;border:1px solid #D5D9DE;display:flex;align-items:center;'
                               f'justify-content:center;font-family:Arial;color:{TEXT_DIM};font-size:16px;">[dashboard screenshot]</div>')
        elif sh.get("paragraphs"):
            body_parts.append(render_text_shape(sh))
        elif "fill" in sh:
            body_parts.append(render_auto_shape(sh))
    body = "\n".join(p for p in body_parts if p)
    html = f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="hz:slide-selector" content=".slide">
<meta name="hz:canvas-width" content="{CW}">
<meta name="hz:canvas-height" content="{CH}">
<style>html,body{{margin:0;padding:0;}}</style>
</head><body>
<div class="slide" data-canvas-width="{CW}" data-canvas-height="{CH}" style="position:relative;width:{CW}px;height:{CH}px;background:{bg};overflow:hidden;font-family:Arial,Helvetica,sans-serif;">
{body}
</div>
</body></html>
"""
    return html


def main():
    for sdata in DATA:
        html = build_slide_html(sdata)
        path = OUT_DIR / f"slide{sdata['slide']:02d}.html"
        path.write_text(html, encoding="utf-8")
        print("wrote", path)


if __name__ == "__main__":
    main()
