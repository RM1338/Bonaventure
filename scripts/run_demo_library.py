"""Run every case in the demo library (~/bonaventure/demo_library) through the full pipeline and write what Bonaventure said
into each folder (result.txt) and into the library index. Reopen any case with ./run.sh BV-xxx.

    PYTHONPATH=. .venv/bin/python scripts/run_demo_library.py
"""
import time
from pathlib import Path

from bonaventure import imaging, pipeline

LIB = Path.home() / "bonaventure/demo_library"

if __name__ == "__main__":
    eng = imaging.ImagingEngine()
    while not eng.ready():
        time.sleep(0.5)
    summary = ["\n## What Bonaventure reports\n", "| Case | Bonaventure case | Result |", "|---|---|---|"]
    for d in sorted(p for p in LIB.iterdir() if p.is_dir()):
        c = pipeline.Case({"path": str(d / "film.png"), "name": f"{d.name}.png"},
                          [{"path": str(d / "history.pdf"), "name": "history.pdf"}], (d / "presentation.txt").read_text())
        c.run(eng)
        r = c.result or {}
        lines = [f"{f['display_name']}: {f['status']} ({f['evidence_strength']})" for f in r.get("findings", [])]
        lines += [f"Also seen: {o['name']}" for o in r.get("other_observations", [])]
        lines += [f"Not assessable on X-ray: {n['name']}" for n in r.get("not_assessable", [])]
        lines = lines or ["No findings"]
        (d / "result.txt").write_text(f"{c.id}\n" + "\n".join(lines) + "\n")
        summary.append(f"| {d.name} | {c.id} | {'; '.join(lines)} |")
        print(f"\n== {d.name}  ->  {c.id}  {c.state}  {r.get('technical', {}).get('total_seconds')}s\n   " + "\n   ".join(lines), flush=True)
    idx = LIB / "README.md"
    text = idx.read_text().split("\n## What Bonaventure reports")[0]
    idx.write_text(text.rstrip() + "\n" + "\n".join(summary) + "\n")
