"""Structure-only scan: quote style, dash dialogue, headings, extraction quality. Prints counts, no book text."""
import re, sys, time
from pathlib import Path
from pypdf import PdfReader
from app.books import reflow

B = Path.home() / "books"
FILES = {
 "Illuminae": "illuminae-by-amie-kaufman-amp-jay-kristoff.pdf",
 "Dark Matter": "_OceanofPDF.com_Dark_Matter_-_Blake_Crouch.pdf",
 "Lincoln Bardo": "Lincoln In The Bardo PDF (Limited Copy).pdf",
 "World War Z": "World War Z_ an oral history of - Max Brooks.pdf",
 "Hail Mary": "Andy Weir;/Project Hail Mary (22)/Project Hail Mary - Andy Weir;.pdf",
 "Frankl": "Steve/Microsoft Word - Man's Search for Meaning by Viktor Frankl.doc (21)/Microsoft Word - Man's Search for Meaning - Steve.pdf",
 "Win Friends": "How to Win Friends and Influence People - Dale Carnegie.pdf",
}
for name, rel in FILES.items():
    t = time.time()
    try:
        r = PdfReader(B / rel); pages = [(p.extract_text() or "") for p in r.pages]
    except Exception as e:
        print(f"{name}: FAILED {e}"); continue
    raw = "\n".join(pages); text = reflow(pages)
    empty = sum(1 for p in pages if len(p.strip()) < 50) / max(len(pages), 1)
    dq = len(re.findall(r'"[^"\n]{3,300}"', text)) + len(re.findall(r"“[^”]{3,300}”", text))
    sq = len(re.findall(r"(?m)(?:^|\s)[‘'][A-Z][^’'\n]{3,200}[’'](?=[\s,.!?])", text))
    dash = len(re.findall(r"(?m)^[—–-]\s?\S", raw))
    heads = len(re.findall(r"(?mi)^\s*(chapter|part|book|section|stave)\s+[\divxlc\w]+", raw))
    caps = len(re.findall(r"(?m)^[A-Z][A-Z .:'’-]{3,40}$", raw))
    words = len(text.split())
    print(f"{name:14} pages={len(pages):4} words={words:7} empty_pg={empty:.0%} dq_quotes={dq:5} sq_quotes={sq:4} dash_lines={dash:4} headings={heads:3} caps_lines={caps:4} ({time.time()-t:.0f}s)", flush=True)
