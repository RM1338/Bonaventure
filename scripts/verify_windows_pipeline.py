"""Run real sample cases through the desktop UI. Close other app instances first.

Run from the repository root: python -m scripts.verify_windows_pipeline
Leaves the positive case open and writes reports/pipeline-acceptance-verification.json.
"""
import base64
import json
import os
import time
import traceback
from pathlib import Path

from bonaventure import app


def wait_for(check, seconds=240):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.4)
    raise TimeoutError("Verification condition timed out")


def main():
    captured = {}
    original_init, original_start = app.Api.__init__, app.webview.start

    def capture(api):
        original_init(api)
        captured["api"] = api

    def verify():
        evidence = {"cases": [], "pid": os.getpid(), "passed": False}
        try:
            api = captured["api"]
            launcher = api._launcher
            wait_for(api._engine.ready)
            assert not api._engine.mock
            assert {"primary", "verifier", "concepts", "reasoning", "segmentation"} <= api._engine.models.keys()
            samples = [
                ("positive", "kerley_b.jpg", "case_a_history.pdf", "Worsening shortness of breath for 3 days, can't lie flat, waking up breathless at night, ankle swelling. No fever, no cough."),
                ("contradiction", "kerley_b.jpg", "case_b_history.pdf", "Breathless for 2 days. Denies fever, cough and ankle swelling."),
                ("normal", "Chest_Xray_PA_3-8-2010.png", None, ""),
            ]
            for label, scan, history, symptoms in samples:
                launcher.evaluate_js("expand()")
                paths = [Path("sample_data/scans") / scan]
                if history:
                    paths.append(Path("sample_data/histories") / history)
                files = [{"name": p.name, "data": base64.b64encode(p.read_bytes()).decode()} for p in paths]
                launcher.evaluate_js('''(() => {const dt = new DataTransfer();
                    for (const p of FILES) dt.items.add(new File([Uint8Array.from(atob(p.data), x => x.charCodeAt(0))], p.name));
                    document.dispatchEvent(new DragEvent("drop", {dataTransfer:dt, bubbles:true, cancelable:true}));
                })()'''.replace("FILES", json.dumps(files)))
                wait_for(lambda: launcher.evaluate_js('pendingUploads===0 && scan!==null && !$("go").disabled'))
                before = set(api._cases)
                launcher.evaluate_js('$("symptoms").value=' + json.dumps(symptoms) + ';$("go").click()')
                cid = wait_for(lambda: next(iter(set(api._cases) - before), None))
                case = api._cases[cid]
                print("START", label, cid, flush=True)
                wait_for(lambda: case.state != "PROCESSING")
                assert case.state == "REVIEW_READY", case.error
                wait_for(lambda: api._review is not None)
                api._review.events.loaded.wait(30)
                wait_for(lambda: api._review.evaluate_js("C && C.case_id") == cid)
                time.sleep(1)
                result = case.result
                dom = api._review.evaluate_js('({text:document.body.innerText, marks:$("ov").children.length, images:[...document.images].filter(i=>i.complete&&i.naturalWidth>0).length})')
                findings = result["findings"]
                audit = {a["model"]: a for a in result["technical"]["model_audit"]}
                assert dom["images"] > 0
                assert all(a["state"] == "complete" for k, a in audit.items() if k != "MedSAM")
                assert result["presentation_text"] == symptoms
                assert result["history_provided"] == bool(history)
                for finding in findings:
                    assert finding["display_name"] in dom["text"]
                if label == "positive":
                    assert any(f["status"] == "SUPPORTED" for f in findings)
                    assert any((f.get("localization") or {}).get("contour") for f in findings)
                    assert audit["MedSAM"]["state"] == "complete" and dom["marks"] > 0
                elif label == "contradiction":
                    assert findings and all(f["status"] == "CONFLICTING" for f in findings)
                else:
                    assert not findings
                    assert case.steps["localize"] == "skipped"
                    assert audit["MedSAM"]["state"] == "skipped"
                    assert "No accepted box to segment." in dom["text"]
                    assert "No accepted image findings" in dom["text"]
                evidence["cases"].append(dict(case=cid, scenario=label,
                    findings=[(f["display_name"], f["status"]) for f in findings],
                    audit=audit, marks=dom["marks"], steps=case.steps))
                print("VERIFIED", label, cid, flush=True)
            evidence["passed"] = True
            api.open_review(evidence["cases"][0]["case"])
        except Exception:
            evidence["error"] = traceback.format_exc()
            print(evidence["error"], flush=True)
        finally:
            Path("reports").mkdir(exist_ok=True)
            Path("reports/pipeline-acceptance-verification.json").write_text(json.dumps(evidence, indent=2))
            print("ACCEPTANCE FINISHED", evidence["passed"], flush=True)

    app.Api.__init__ = capture
    app.webview.start = lambda **kw: original_start(verify, **kw)
    app.main()


if __name__ == "__main__":
    main()
