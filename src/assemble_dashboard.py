"""Assembles the standalone dashboard HTML from template + data + app.js."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
D = ROOT / "dashboard"

template = (D / "template.html").read_text(encoding="utf-8")
app_js = (D / "app.js").read_text(encoding="utf-8")
locations = (D / "data" / "locations.json").read_text(encoding="utf-8")
evidence = (D / "data" / "evidence.json").read_text(encoding="utf-8")
meta = (D / "data" / "meta.json").read_text(encoding="utf-8")

out = template.replace("/*__LOCATIONS_JSON__*/", locations) \
              .replace("/*__EVIDENCE_JSON__*/", evidence) \
              .replace("/*__META_JSON__*/", meta) \
              .replace("/*__APP_JS__*/", app_js)

out_path = ROOT / "QSR_Location_Health_Dashboard.html"
out_path.write_text(out, encoding="utf-8")
print(f"Wrote {out_path} ({out_path.stat().st_size / 1e6:.2f} MB)")
