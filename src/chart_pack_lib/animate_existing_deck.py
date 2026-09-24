"""
Adds PowerPoint transitions (Morph/Wipe/Fade) and within-slide entrance-animation
timing to the EXISTING, already-built QSR_LHI_Presentation.pptx (17 slides, native
PowerPoint charts + shapes). Does NOT touch any shape's position, size, color, text,
or the chart data -- purely additive OOXML (<p:transition>, <p:timing>) on top of the
untouched shape tree, per the explicit instruction to keep content/design as-is.

Reads QSR_LHI_Presentation.pptx from the project root (read-only) and writes
QSR_LHI_Presentation_animated.pptx alongside it -- the original is never overwritten.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pptx import Presentation
from deck_anim import set_transition, TimingBuilder

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "QSR_LHI_Presentation.pptx"
OUT = ROOT / "QSR_LHI_Presentation_animated.pptx"

# background rect (id=2, top=0/left=0 full-bleed) is present on every slide and is
# never animated -- it and the page-number textbox (bottom-right, skipped per-slide
# below) are the only shapes intentionally excluded from all timing.

# transition used when ARRIVING at slide N (1-indexed). No Morph anywhere, per
# explicit instruction -- Fade only, on every slide. The real motion is the
# within-slide entrance build below (every element animates in on arrival).
TRANSITIONS = {i: "fade" for i in range(1, 18)}

WIPE_R, WIPE_D, WIPE_U, FADE = "wipe-right", "wipe-down", "wipe-up", "fade"

# per-slide beats: list of (effect, [shape_ids], stagger_ms, dur_ms)
# stagger_ms = gap from the PREVIOUS beat's start (not previous shape); shapes
# within one beat fire together (same delay), each shape's own dur_ms controls
# how long its own entrance takes.
BEATS = {
    1: [
        (FADE, [3, 4], 0, 500),
        (FADE, [5], 500, 450),
        (FADE, [6], 950, 400),
    ],
    2: [
        (FADE, [3, 4], 0, 450),
        (FADE, [5], 450, 400),
        (WIPE_R, [6, 7, 8], 950, 350),
        (WIPE_R, [9, 10, 11], 1150, 350),
        (WIPE_R, [12, 13, 14], 1350, 350),
        (WIPE_R, [15, 16, 17], 1550, 350),
        (FADE, [18], 2000, 400),
    ],
    3: [
        (FADE, [3, 4], 0, 450),
        (WIPE_D, [5, 6, 7, 8], 500, 350),
        (WIPE_D, [9, 10, 11, 12], 850, 350),
        (WIPE_D, [13, 14, 15, 16], 1200, 350),
        (WIPE_D, [17, 18, 19, 20], 1550, 350),
        (FADE, [21, 22], 2050, 400),
    ],
    5: [
        (FADE, [3, 4], 0, 450),
        (FADE, [5], 450, 400),
        (WIPE_U, [10], 900, 500),
        (WIPE_R, [6, 7, 8, 9], 1450, 350),
    ],
    6: [
        (FADE, [3, 4], 0, 450),
        (WIPE_R, [5, 6, 7, 8, 9], 500, 350),
        (WIPE_R, [10, 11, 12, 13, 14], 750, 350),
        (WIPE_R, [15, 16, 17, 18, 19], 1200, 350),
        (WIPE_R, [20, 21, 22, 23, 24], 1450, 350),
        (FADE, [25, 26], 1900, 400),
    ],
    7: [
        (FADE, [3, 4], 0, 450),
        (WIPE_U, [5], 500, 500),
        (FADE, [6, 7], 1100, 400),
        (FADE, [8, 9, 10], 1550, 400),
    ],
    8: [
        (FADE, [3, 4], 0, 450),
        (WIPE_U, [5], 500, 500),
        (WIPE_D, [6, 7, 8], 1100, 300),
        (WIPE_D, [9, 10, 11], 1300, 300),
        (WIPE_D, [12, 13, 14], 1500, 300),
        (WIPE_D, [15, 16, 17], 1700, 300),
        (FADE, [18, 19, 20], 2150, 400),
    ],
    9: [
        (FADE, [3, 4], 0, 450),
        (FADE, [5, 6, 7, 8, 9, 10, 11], 500, 450),
        (WIPE_R, [12, 13, 14], 1100, 350),
        (WIPE_R, [15, 16, 17], 1350, 350),
        (WIPE_R, [18, 19, 20], 1600, 350),
        (WIPE_R, [21, 22, 23], 1850, 350),
        (FADE, [24, 25, 26], 2300, 400),
        (FADE, [27], 2650, 400),
    ],
    10: [
        (FADE, [3, 4], 0, 450),
        (WIPE_U, [5], 500, 500),
        (FADE, [6, 7], 1100, 400),
        (FADE, [8, 9], 1500, 400),
    ],
    11: [
        # consolidated from 13 one-by-one beats to 7 grouped ones: the 4 stat chips
        # are a single "vital signs" glance, not a sequential argument, so they
        # populate together; same for the 4 pillar bars. Restraint over busywork.
        (FADE, [3, 4, 5, 6], 0, 500),
        (WIPE_R, [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18], 600, 350),
        (FADE, [19], 1200, 300),
        (WIPE_R, [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35], 1550, 400),
        (FADE, [36], 2150, 350),
        (WIPE_U, [37], 2500, 450),
        (FADE, [38, 39, 40], 3050, 400),
    ],
    12: [
        (FADE, [3, 4], 0, 450),
        (WIPE_U, [5], 500, 500),
        (FADE, [6, 7], 1100, 400),
        (FADE, [8, 9, 10], 1500, 400),
        (FADE, [11, 12], 1900, 400),
    ],
    13: [
        (FADE, [3, 4], 0, 450),
        (WIPE_U, [5], 500, 500),
        (FADE, [6, 7], 1100, 400),
        (FADE, [8, 9, 10], 1500, 400),
    ],
    14: [
        (FADE, [3, 4], 0, 450),
        (WIPE_U, [5], 500, 500),
        (FADE, [6, 7], 1100, 400),
        (FADE, [8, 9], 1500, 400),
    ],
    15: [
        (FADE, [3, 4], 0, 450),
        (WIPE_R, [6, 5], 500, 550),
        (WIPE_D, [7, 8, 9], 1150, 350),
        (WIPE_D, [10, 11, 12], 1400, 350),
        (WIPE_D, [13, 14, 15], 1650, 350),
    ],
    16: [
        (FADE, [3, 4], 0, 450),
        (WIPE_D, [5, 6, 7, 8], 500, 300),
        (WIPE_D, [9, 10, 11, 12], 750, 300),
        (WIPE_D, [13, 14, 15, 16], 1000, 300),
        (WIPE_D, [17, 18, 19, 20], 1250, 300),
        (WIPE_D, [21, 22, 23, 24], 1500, 300),
    ],
    17: [
        (FADE, [3, 4], 0, 450),
        (WIPE_D, [5, 6, 7], 500, 300),
        (WIPE_D, [8, 9, 10], 750, 300),
        (WIPE_D, [11, 12, 13], 1000, 300),
        (WIPE_D, [14, 15, 16], 1250, 300),
        (FADE, [17], 1650, 400),
    ],
}
# slide 4 (13-stage pipeline) built programmatically below -- too regular to hand-list


def build_slide4_beats():
    beats = [(FADE, [3, 4], 0, 450)]
    delay = 500
    for k in range(12):
        ids = [5 + 4 * k, 6 + 4 * k, 7 + 4 * k, 8 + 4 * k]
        beats.append((WIPE_R, ids, delay, 250))
        delay += 130
    beats.append((WIPE_R, [53, 54, 55], delay, 250))
    delay += 250
    for ids in ([56, 57, 58], [59, 60, 61], [62, 63, 64], [65, 66, 67]):
        beats.append((WIPE_D, ids, delay, 300))
        delay += 200
    beats.append((FADE, [68], delay + 200, 400))
    return beats


BEATS[4] = build_slide4_beats()


def main():
    # Custom <p:timing>/<p:bldLst> entrance animation is DISABLED. Two attempts at
    # hand-written OOXML animation timing both failed in the user's real PowerPoint
    # (first: nothing animated; second: content stayed hidden -- blank slides). This
    # environment has no PowerPoint/LibreOffice to test that XML against, so a third
    # blind attempt is not responsible. Only <p:transition> (Fade) is applied below --
    # that is simple, well-tested XML with no hidden/reveal state to get wrong, so a
    # mistake there degrades to "no transition," never "invisible content."
    prs = Presentation(str(SRC))
    slides = list(prs.slides)
    assert len(slides) == 17, f"expected 17 slides, found {len(slides)} -- deck structure changed?"

    for idx, slide in enumerate(slides, 1):
        shape_by_id = {sh.shape_id: sh for sh in slide.shapes}
        for effect, ids, delay_ms, dur_ms in BEATS.get(idx, []):
            for sid in ids:
                if sid not in shape_by_id:
                    raise KeyError(f"slide {idx}: shape id {sid} not found (deck structure changed?)")
        set_transition(slide, TRANSITIONS[idx])

    prs.save(str(OUT))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
