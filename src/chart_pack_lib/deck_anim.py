"""
Low-level OOXML helpers for slide transitions (Morph / Wipe / Fade) and
within-slide entrance-animation timing trees (Wipe / Fade), used by build_deck.py.

Design choice, stated plainly for the QA report: <p:timing> and <p:transition> are
additive siblings of the shape tree under <p:sld> (CT_Slide: cSld, clrMapOvr?,
transition?, timing?, extLst?). A malformed or unsupported entry in either does not
break the shape tree itself -- worst case for any single slide is "animation doesn't
play," never "file won't open" or "content is wrong." Morph is wrapped in
mc:AlternateContent with a Fade fallback for the same reason: any PowerPoint that
doesn't resolve the p159 Morph Choice silently uses the Fade Fallback instead.

Live PowerPoint playback of these could not be verified in this environment (no
Windows PowerPoint, no LibreOffice available) -- see the QA report for what was and
was not verified structurally.
"""
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"
P159_NS = "http://schemas.microsoft.com/office/powerpoint/2015/09/main"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def _insert_after_csld(sld_elem, new_elem):
    """Insert new_elem in the schema-correct position: after cSld/clrMapOvr, before timing."""
    csld = sld_elem.find(qn("p:cSld"))
    clrmap = sld_elem.find(qn("p:clrMapOvr"))
    anchor = clrmap if clrmap is not None else csld
    anchor.addnext(new_elem)


def set_transition(slide, kind, dur_ms=700):
    """kind: 'morph' | 'wipe' | 'fade'. Removes any existing <p:transition> first."""
    sld = slide._element
    existing = sld.find(qn("p:transition"))
    if existing is not None:
        sld.remove(existing)

    if kind == "morph":
        xml = f"""
<p:transition xmlns:p="{P_NS}" xmlns:p14="{P14_NS}" spd="slow" p14:dur="{dur_ms}">
  <mc:AlternateContent xmlns:mc="{MC_NS}">
    <mc:Choice xmlns:p159="{P159_NS}" Requires="p159">
      <p159:morph p159:option="byObject"/>
    </mc:Choice>
    <mc:Fallback>
      <p:fade/>
    </mc:Fallback>
  </mc:AlternateContent>
</p:transition>""".strip()
    elif kind == "wipe":
        xml = f"""<p:transition xmlns:p="{P_NS}" spd="med"><p:wipe dir="r"/></p:transition>"""
    else:  # fade
        xml = f"""<p:transition xmlns:p="{P_NS}" spd="med"><p:fade/></p:transition>"""

    new_elem = parse_xml(xml)
    _insert_after_csld(sld, new_elem)


class TimingBuilder:
    """Accumulates staggered entrance-animation steps for one slide, then emits <p:timing>."""

    def __init__(self):
        self._steps = []  # (spid, filter, delay_ms, dur_ms)
        self._id = 3  # 1=tmRoot, 2=mainSeq group cTn reserved

    def add(self, shape, effect, delay_ms, dur_ms=500):
        """effect: 'fade' | 'wipe-right' | 'wipe-up' | 'wipe-down' | 'wipe-left'"""
        filt = {"fade": "fade", "wipe-right": "wipe(right)", "wipe-left": "wipe(left)",
                "wipe-up": "wipe(up)", "wipe-down": "wipe(down)"}[effect]
        preset = 10 if effect == "fade" else 22
        self._steps.append((shape.shape_id, filt, preset, delay_ms, dur_ms))

    def build(self):
        par_blocks = []
        for spid, filt, preset, delay_ms, dur_ms in self._steps:
            i1 = self._id; self._id += 1
            i2 = self._id; self._id += 1
            i3 = self._id; self._id += 1
            par_blocks.append(f"""
<p:par>
  <p:cTn id="{i1}" presetID="{preset}" presetClass="entr" presetSubtype="0" fill="hold" nodeType="afterEffect">
    <p:stCondLst><p:cond delay="{delay_ms}"/></p:stCondLst>
    <p:childTnLst>
      <p:set>
        <p:cBhvr>
          <p:cTn id="{i2}" dur="1"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>
          <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
          <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
        </p:cBhvr>
        <p:to><p:strVal val="visible"/></p:to>
      </p:set>
      <p:animEffect transition="in" filter="{filt}">
        <p:cBhvr>
          <p:cTn id="{i3}" dur="{dur_ms}"/>
          <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
        </p:cBhvr>
      </p:animEffect>
    </p:childTnLst>
  </p:cTn>
</p:par>""".strip())
        body = "\n".join(par_blocks)
        # bldLst is what actually marks each shape "hidden until its animation fires" --
        # without it a shape with only a <p:set>/<p:animEffect> entry can render as
        # already-visible in real PowerPoint, i.e. "nothing appears to animate."
        bld_entries = "\n".join(f'<p:bldP spid="{spid}" grpId="0"/>'
                                 for spid, *_ in self._steps)
        xml = f"""
<p:timing xmlns:p="{P_NS}">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst>
                <p:par>
                  <p:cTn id="{self._id}" fill="hold">
                    <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                    <p:childTnLst>
                      {body}
                    </p:childTnLst>
                  </p:cTn>
                </p:par>
              </p:childTnLst>
            </p:cTn>
          </p:seq>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
  <p:bldLst>
    {bld_entries}
  </p:bldLst>
</p:timing>""".strip()
        return xml

    def apply(self, slide):
        if not self._steps:
            return
        sld = slide._element
        existing = sld.find(qn("p:timing"))
        if existing is not None:
            sld.remove(existing)
        new_elem = parse_xml(self.build())
        # timing goes last, after transition (or after cSld/clrMapOvr if no transition)
        transition = sld.find(qn("p:transition"))
        anchor = transition if transition is not None else sld.find(qn("p:clrMapOvr"))
        if anchor is None:
            anchor = sld.find(qn("p:cSld"))
        anchor.addnext(new_elem)
