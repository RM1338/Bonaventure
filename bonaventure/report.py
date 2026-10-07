"""Evidence Report: annotated X-ray + per-finding evidence, rendered to PDF with WeasyPrint."""
import base64
import io
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .pipeline import ROOT

REPORTS = ROOT / "reports"
ORANGE = (234, 120, 30)
STATUS_LABEL = {"SUPPORTED": "Supported", "UNCERTAIN": "Uncertain", "CONFLICTING": "Conflicting", "INSUFFICIENT_EVIDENCE": "Insufficient evidence"}


def annotate(scan_png, findings):
    """Grayscale scan + thin orange contour, leader line and label per localized finding (no tinting of the scan)."""
    img = Image.open(scan_png).convert("RGB")
    w, h = img.size
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", max(14, w // 55))
    except OSError:
        font = ImageFont.load_default()
    for f in findings:
        loc = f.get("localization")
        if not loc or f["status"] == "INSUFFICIENT_EVIDENCE":
            continue
        x0, y0, x1, y1 = loc["coordinates"]
        box = [x0 * w, y0 * h, x1 * w, y1 * h]
        if loc.get("contour"):  # MedSAM outline, as on screen
            d.line([(x * w, y * h) for x, y in loc["contour"] + loc["contour"][:1]], fill=ORANGE, width=max(2, w // 400), joint="curve")
        else:
            d.ellipse(box, outline=ORANGE, width=max(2, w // 400))
        right = box[2] < w * 0.6
        ax, ay = (box[2], (box[1] + box[3]) / 2) if right else (box[0], (box[1] + box[3]) / 2)
        tx = ax + w * 0.06 if right else ax - w * 0.06
        d.line([ax, ay, tx, ay], fill=ORANGE, width=max(2, w // 500))
        label = f["display_name"]
        tw = d.textlength(label, font=font)
        d.text((tx + 6 if right else tx - tw - 6, ay - font.size * 0.6), label, fill=ORANGE, font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _li(items):
    return "".join(f"<li>{x}</li>" for x in items) or "<li class='none'>None identified</li>"


def _src(s):
    return f"<span class='src'>{escape(s['doc_type'])} · {escape(s['file'])} · page {s['page']}</span>"


def render_html(case):
    findings = case["findings"]
    img = annotate(Path(ROOT / "cases" / case["case_id"] / "scan.png"), findings)
    present = [s for s in case["symptoms"] if s["state"] == "present"]
    denied = [s for s in case["symptoms"] if s["state"] == "denied"]
    q = case["quality"]
    blocks = []
    for i, f in enumerate(findings, 1):
        hist = [f"{escape(e['text'])}{' · ' + e['date'] if e['date'] else ''}<br>{_src(e['source'])}" for e in f["history_evidence"]]
        blocks.append(f"""
        <section class="finding">
          <div class="fhead"><span class="num">Finding {i:02d}</span><h3>{escape(f['display_name'])}</h3>
            <span class="status s-{f['status']}">{STATUS_LABEL[f['status']]}</span></div>
          <p class="ct">{escape(f['clinician_text'])}</p>
          <div class="cols">
            <div><h4>Image evidence</h4><ul>{_li(escape(e['text']) for e in f['image_evidence'])}</ul></div>
            <div><h4>Relevant history</h4><ul>{_li(hist)}</ul></div>
            <div><h4>Current presentation</h4><ul>{_li(escape(s['text'] + (' · ' + s['duration'] if s['duration'] else '')) for s in f['symptom_evidence'])}</ul></div>
          </div>
          <div class="cols">
            <div class="wide"><h4>Conflicting / negative evidence</h4><ul>{_li([escape(c) for c in f['contradictions']] + [escape(n['text']) for n in f['negative_evidence']])}</ul></div>
            <div><h4>Evidence strength</h4><p class="strength">{f['evidence_strength'].upper()}</p></div>
          </div>
        </section>""")
    timeline = "".join(f"<tr><td>{e['date'] or '—'}</td><td>{escape(e['label'])}</td><td>{_src(e['source'])}</td></tr>" for e in case["timeline"]) \
        or "<tr><td colspan=3 class='none'>" + ("No relevant history identified." if case["history_provided"] else "Patient history not provided. Clinical context support is unavailable.") + "</td></tr>"
    models = ", ".join(f"{m['model']} ({m['role']})" for m in case["technical"]["models"])
    if "MedGemma" in case["technical"].get("timing", {}):
        models += ", MedGemma 1.5 4B (localization and visual description)"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    @page {{ size: A4; margin: 16mm 15mm 18mm; @bottom-center {{ content: "Bonaventure Evidence Report · {case['case_id']} · page " counter(page); font: 8pt sans-serif; color: #6b7a90; }} }}
    body {{ font-family: "Inter", "DejaVu Sans", sans-serif; color: #14233a; font-size: 9.5pt; line-height: 1.45; }}
    .brand {{ letter-spacing: .18em; font-weight: 700; font-size: 10pt; color: #1d5fd1; }}
    .tag {{ color: #6b7a90; font-size: 8.5pt; }}
    h1 {{ font-size: 17pt; margin: 10px 0 2px; }} h2 {{ font-size: 11pt; border-bottom: 1px solid #d8e1ee; padding-bottom: 3px; margin-top: 18px; }}
    h3 {{ display: inline; font-size: 12pt; margin: 0 8px; }} h4 {{ font-size: 8pt; letter-spacing: .08em; text-transform: uppercase; color: #6b7a90; margin: 8px 0 3px; }}
    .meta td {{ padding: 1px 14px 1px 0; }} .scan {{ text-align: center; background: #0b0f16; padding: 8px; border-radius: 8px; }}
    .scan img {{ max-height: 115mm; max-width: 100%; }}
    .finding {{ border: 1px solid #d8e1ee; border-radius: 10px; padding: 10px 12px; margin: 10px 0; page-break-inside: avoid; }}
    .num {{ color: #6b7a90; font-size: 8pt; }} .status {{ float: right; font-weight: 700; font-size: 8.5pt; padding: 2px 8px; border-radius: 10px; }}
    .s-SUPPORTED {{ background: #e3f5ea; color: #17803d; }} .s-UNCERTAIN {{ background: #fff4dc; color: #a86a00; }}
    .s-CONFLICTING {{ background: #fde8e8; color: #b42318; }} .s-INSUFFICIENT_EVIDENCE {{ background: #edf1f6; color: #4a5a70; }}
    .cols {{ display: flex; gap: 12px; }} .cols > div {{ flex: 1; }} .cols > .wide {{ flex: 2; }}
    ul {{ margin: 0; padding-left: 14px; }} .none {{ color: #8a97a8; list-style: none; margin-left: -14px; }}
    .src {{ color: #6b7a90; font-size: 7.5pt; }} .strength {{ font-weight: 700; font-size: 12pt; margin: 0; }}
    .ct {{ margin: 6px 0 2px; }} table {{ border-collapse: collapse; width: 100%; }} td {{ vertical-align: top; padding: 3px 6px 3px 0; }}
    .warn {{ background: #fff4dc; border-left: 3px solid #e0a100; padding: 6px 10px; border-radius: 4px; }}
    .limits {{ color: #4a5a70; font-size: 8.5pt; }}
    </style></head><body>
    <div class="brand">BONAVENTURE</div><div class="tag">Clinical Evidence Intelligence</div>
    <h1>Clinical Evidence Review</h1>
    <table class="meta"><tr><td><b>Case</b> {case['case_id']}</td><td><b>Generated</b> {case['created'].replace('T', ' ')}</td>
      <td><b>Study</b> {escape(case['scan']['view'])} · {case['scan']['width']}×{case['scan']['height']}</td></tr></table>
    <h2>Current presentation</h2>
    <p>{escape(case['presentation_text']) or '<span class="none">Not provided.</span>'}</p>
    <p><b>Present:</b> {escape(', '.join(s['label'] + (' (' + s['duration'] + ')' if s['duration'] else '') for s in present)) or '—'}
       &nbsp; <b>Denied:</b> {escape(', '.join(s['label'] for s in denied)) or '—'}</p>
    <h2>Relevant patient history</h2><table>{timeline}</table>
    <h2>Chest X-ray assessment</h2>
    {'<p class="warn"><b>Image quality: ' + q['state'] + '.</b> ' + escape(' '.join(q['warnings'])) + '</p>' if q['warnings'] else ''}
    <div class="scan"><img src="{img}"></div>
    <p><b>{case['summary']['total']}</b> candidate finding(s): {', '.join(f"{n} {STATUS_LABEL[s].lower()}" for s, n in case['summary']['counts'].items() if n) or 'none'}.
       Overall evidence quality: <b>{case['summary']['overall_quality'].upper()}</b>.</p>
    {''.join(blocks) or '<p class="none">' + escape(case['summary']['message'] or '') + '</p>'}
    {('<h2>Not assessable on a chest X-ray</h2>' + ''.join(f"<p><b>{escape(n['name'])}</b> — raised by {escape(', '.join(n['because']).lower())}. {escape(n['advice'])}</p>" for n in case.get('not_assessable', []))) if case.get('not_assessable') else ''}
    {('<h2>Other observations (single reader, unverified)</h2><ul>' + ''.join(f"<li>{escape(o['name'])}{' — ' + escape(o['region']) if o.get('region') else ''} <span class='src'>{escape(o['source'])}</span></li>" for o in case.get('other_observations', [])) + '</ul>') if case.get('other_observations') else ''}
    <h2>Limitations</h2>
    <p class="limits">Findings are candidate observations generated by automated models and reconciled against the supplied documents.
    Evidence strength is a rule-based summary of agreement between sources, not a calibrated probability. Localization is approximate.
    {escape(' '.join(q['warnings']))} Models used: {escape(models)}.</p>
    <h2>Review statement</h2>
    <p>This report is generated as clinical decision support from the supplied imaging and contextual evidence.
    It is not a definitive diagnosis and requires review by a qualified clinician.</p>
    </body></html>"""


def generate(case):
    from weasyprint import HTML
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{case['case_id']}.pdf"
    HTML(string=render_html(case)).write_pdf(out)
    return out
