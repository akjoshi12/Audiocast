"""python -m scripts.try_books  -> label an excerpt of each test book with two models, report agreement.
Outputs go to samples/trial/<name>/{script.json,report.json}. Prints counts only."""
import json, time, warnings, logging
from collections import Counter
from pathlib import Path
from pypdf import PdfReader
from app import annotate
from app.books import reflow

logging.disable(logging.CRITICAL); warnings.filterwarnings("ignore")
B = Path.home() / "books"
TRIALS = {  # name: (file, first page, last page)  (1-based, inclusive)
 "hail_mary":  ("Andy Weir;/Project Hail Mary (22)/Project Hail Mary - Andy Weir;.pdf", 100, 104),
 "world_war_z": ("World War Z_ an oral history of - Max Brooks.pdf", 60, 66),
 "lincoln_bardo": ("Lincoln In The Bardo PDF (Limited Copy).pdf", 40, 48),
 "illuminae": ("illuminae-by-amie-kaufman-amp-jay-kristoff.pdf", 12, 20),
 "frankl": ("Steve/Microsoft Word - Man's Search for Meaning by Viktor Frankl.doc (21)/Microsoft Word - Man's Search for Meaning - Steve.pdf", 20, 26),
}
for name, (rel, a, b) in TRIALS.items():
    out = Path("samples/trial") / name; out.mkdir(parents=True, exist_ok=True)
    t = time.time()
    pages = [(p.extract_text() or "") for p in PdfReader(B / rel).pages[a - 1:b]]
    text = reflow(pages)
    q = annotate.annotate_chapter(text)
    g = annotate.annotate_chapter(text, model="google/gemma-4-e4b")
    ag = annotate.agreement(q["units"], g["units"])
    kinds = Counter(u["kind"] for u in q["units"])
    speakers = Counter(u["speaker"] for u in q["units"] if u["speaker"] != "Narrator")
    rep = {"chars": len(text), "units": ag["units"], "lines": len(q["lines"]), "kinds": dict(kinds),
           "speakers": dict(speakers.most_common(8)), "unsure": sum(u["unsure"] for u in q["units"]),
           "disagree": ag["disagree"], "disagree_rate": round(ag["rate"], 3), "secs": round(time.time() - t)}
    (out / "script.json").write_text(json.dumps({"title": name, "characters": q["characters"], "units": q["units"],
                                                 "lines": q["lines"], "disagree_ids": ag["ids"]}, indent=1))
    (out / "excerpt.txt").write_text(text)
    (out / "report.json").write_text(json.dumps(rep, indent=1))
    print(name, json.dumps(rep), flush=True)
