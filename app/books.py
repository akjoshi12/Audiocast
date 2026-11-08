"""Book -> chapters. EPUB (spine order), PDF and TXT (heading regex)."""
import re
from functools import lru_cache
from pathlib import Path

CHAPTER_RE = re.compile(r"^\s*(chapter\s+[\divxlc]+\b.*|prologue|epilogue)\s*$", re.I | re.M)


def _split_by_headings(text: str) -> list[dict]:
    marks = list(CHAPTER_RE.finditer(text))
    if not marks:
        return [{"title": "Full text", "text": text.strip()}]
    # headings also appear in the table of contents, cross-references and endnotes: keep the in-order run of chapter
    # numbers that covers the most text (weighted longest increasing subsequence)
    span = lambda i: (marks[i + 1].start() if i + 1 < len(marks) else len(text)) - marks[i].end()
    num = lambda m: int(n.group(1)) if (n := re.match(r"chapter\s+(\d+)", m.group(1), re.I)) else None
    nums = [i for i, m in enumerate(marks) if num(m) is not None]
    best, prev = {}, {}
    for i in nums:
        j = max((j for j in best if num(marks[j]) < num(marks[i])), key=best.get, default=None)
        best[i], prev[i] = span(i) + (best[j] if j is not None else 0), j
    keep, i = set(), max(best, key=best.get, default=None)  # ponytail: a book whose numbering restarts per part loses a part
    while i is not None:
        keep.add(i); i = prev[i]
    marks = [m for i, m in enumerate(marks) if num(m) is None or i in keep]
    if not marks:
        return [{"title": "Full text", "text": text.strip()}]
    out = []
    if marks[0].start() > 200:  # front matter worth keeping
        out.append({"title": "Opening", "text": text[: marks[0].start()].strip()})
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append({"title": re.sub(r"^chapter\b", "Chapter", m.group(1).strip(), flags=re.I), "text": text[m.end():end].strip()})
    return out


def _epub(path: Path) -> list[dict]:
    from bs4 import BeautifulSoup
    from ebooklib import ITEM_DOCUMENT, epub

    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    out = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):  # spine order
        soup = BeautifulSoup(item.get_content(), "lxml")
        head = soup.find(["h1", "h2", "h3"])
        title = head.get_text(" ", strip=True) if head else item.get_name()
        # one line per paragraph so later stages see paragraph breaks
        paras = [p.get_text(" ", strip=True) for p in soup.find_all(["p", "h1", "h2", "h3"])]
        text = "\n\n".join(p for p in paras if p)
        if len(text) > 200:  # drops cover/toc/copyright stubs
            out.append({"title": title, "text": text})
    return out


END_RE = re.compile(r"[.!?…][\"”’')]*$")


URL_RE = re.compile(r"(?:https?:\s*//|www\.)\s*\S+|\b[\w.+-]+@[\w-]+\.[\w.]+\b", re.I)
_norm = lambda l: re.sub(r"\d+", "#", l.strip().lower())


def running_junk(pages: list[str]) -> set[str]:
    """Lines that repeat at the top/bottom of many pages (running titles, watermarks, "Page 12 of 300") and are
    hardly ever seen elsewhere. Chapter headings are never junk."""
    edge, total, heading = {}, {}, set()
    for p in pages:
        ls = [l.strip() for l in p.split("\n") if l.strip()]
        for k, l in enumerate(ls):
            n = _norm(l)
            if CHAPTER_RE.fullmatch(l):
                heading.add(n)
            total[n] = total.get(n, 0) + 1
            if k < 2 or k >= len(ls) - 2:
                edge[n] = edge.get(n, 0) + 1
    # ponytail: needs >=4 pages, so a 3-page excerpt keeps its footer
    return {n for n, c in edge.items() if c >= 4 and c >= 0.8 * total[n] and 2 <= len(n) < 100 and n not in heading}


DROPCAP = "\x01"   # marks a line that begins with a re-attached drop cap: it starts a paragraph and is never part of a heading's title
LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})


@lru_cache(maxsize=1)
def _words() -> frozenset[str]:
    """System word list (macOS/Linux). Empty if absent: the checks below then fall back to the book's own vocabulary."""
    try:
        return frozenset(w.strip().lower() for w in Path("/usr/share/dict/words").read_text(errors="ignore").splitlines())
    except OSError:
        return frozenset()


def _join_hyphen(left: str, right: str, vocab: set[str]) -> bool:
    """Line ended "cate-" and the next began "gory": drop the hyphen if the joined word is real, keep it for compounds ("half-past")."""
    whole, known = (left + right).lower(), _words()
    if whole in known or whole in vocab:
        return True
    return bool(known) and not (left.lower() in known and right.lower() in known)


def reflow(pages: list[str], drop: set[str] = frozenset(), title: str = "") -> str:
    """PDF text -> paragraphs separated by blank lines.
    PDFs hard-wrap lines and give no paragraph marks, so a short line ending in sentence
    punctuation (or an ALL-CAPS header line) is treated as a paragraph end."""
    lines = []
    for p in pages:
        p = p.translate(LIGATURES).replace("\t", " ").replace("\xa0", " ")
        p = re.sub(r"^\s*\d{1,3} (?=[a-z])", "", p)  # page number glued to the first line
        lines += [l.strip() for l in p.split("\n")]
    lines = [URL_RE.sub("", l).strip() for l in lines if _norm(l) not in drop]  # repeated headers/footers; links and emails
    lines = [l for l in lines if not re.fullmatch(r"\d{1,3}", l) and ".indd" not in l]  # page numbers, InDesign print footers
    known, merged, k = _words(), [], 0
    while k < len(lines):  # drop cap: the big first letter comes out as a line of its own ("I" / "n the year 1878")
        nxt = re.match(r"[a-z]+", lines[k + 1]) if k + 1 < len(lines) else None
        if nxt and re.fullmatch(r"[A-Z]", lines[k]) and (lines[k] not in "AI" or (lines[k] + nxt.group()).lower() in known):  # a lone "I"/"A" is a word
            merged.append(DROPCAP + lines[k] + lines[k + 1]); k += 2
        else:
            merged.append(lines[k]); k += 1
    lines = merged
    vocab = {w for l in lines for w in re.findall(r"[a-z]+", l.lower())}
    sizes = sorted(len(l.lstrip(DROPCAP)) for l in lines if l)
    width = sizes[int(len(sizes) * 0.9)] if sizes else 0
    paras, cur = [], ""
    i = 0
    while i < len(lines):
        l = lines[i]; i += 1
        if l.startswith(DROPCAP):
            if cur: paras.append(cur); cur = ""
            l = l[1:]
        if not l:
            if cur: paras.append(cur); cur = ""
            continue
        if CHAPTER_RE.fullmatch(l):  # heading gets its own paragraph; "CHAPTER 1" + next short line(s) = its title
            if cur: paras.append(cur); cur = ""
            if re.fullmatch(r"chapter\s+[\divxlc]+\.?", l, re.I):
                t, want = [], _squash(re.split(r"\s*[—–:]\s*", title, maxsplit=1)[-1])[0] if title else ""
                if want:  # the bookmark says what the title is: take exactly the lines that spell it
                    while i < len(lines) and lines[i] and want.startswith(_squash("".join(t) + lines[i])[0]):
                        t.append(lines[i]); i += 1
                else:  # no bookmark: short lines that do not look like sentences
                    while i < len(lines) and len(t) < 3 and lines[i] and not lines[i].startswith(DROPCAP) and len(lines[i]) < 0.8 * width and not lines[i].isupper() and not END_RE.search(lines[i]):
                        t.append(lines[i]); i += 1
                l = f"{l.rstrip('.')}: {' '.join(t)}" if t else l
            paras.append(l)
            continue
        if cur.endswith("-") and l[:1].islower():
            a, b = re.search(r"([A-Za-z]+)-$", cur), re.match(r"[A-Za-z]+", l)
            cur = (cur[:-1] if a and b and _join_hyphen(a.group(1), b.group(), vocab) else cur) + l
        else:
            cur = f"{cur} {l}".strip()
        if (l.isupper() and len(l) < 60) or (END_RE.search(l) and len(l) < 0.75 * width):
            paras.append(cur); cur = ""
    if cur: paras.append(cur)
    # ALL-CAPS header lines ("LOG ENTRY: SOL 6") are read badly by TTS; make them sentences
    paras = [p.capitalize() + "." if p.isupper() and not END_RE.search(p) else p for p in paras]
    text = re.sub(r" {2,}", " ", URL_RE.sub("", "\n\n".join(paras)))
    return re.sub(r"’ (?=\d)", "’", re.sub(r" ’(?=[a-z])", "’", text))  # "o ’clock", "years ’ 82": stray space from kerning  # last, so links wrapped across lines/paragraphs go too


SKIP_RE = re.compile(r"(title page|cover|copyright|epigraph|dedication|contents|table of contents|acknowledg\w*|notes|index|"
                     r"about the authors?|also by.*|praise.*|bibliography|references|credits)\W*$", re.I)


def _squash(text: str) -> tuple[str, list[int]]:
    idx = [i for i, c in enumerate(text) if c.isalnum()]
    return "".join(text[i].lower() for i in idx), idx


def _roman(n: int) -> str:
    out = ""
    for v, sym in ((10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= v:
            out += sym; n -= v
    return out


def cut_offset(text: str, title: str) -> int:
    """Where a chapter really starts inside its first page. Bookmarks point at the page, but chapters often begin halfway down it,
    and the part above belongs to the previous chapter. 0 = top of the page or not found."""
    parts = re.split(r"\s*[—–:]\s*", title, maxsplit=1)
    head, tail = parts[0], parts[1] if len(parts) > 1 else ""
    desc = _squash(tail or head)[0]
    sq, idx = _squash(text)
    cands, j = [], sq.find(desc) if len(desc) >= 6 and not re.fullmatch(r"chapter\d+", desc) else -1
    while j != -1:
        cands.append(idx[j]); j = sq.find(desc, j + 1)
    num = re.fullmatch(r"(?:chapter\s+)?(\d+)", head.strip(), re.I)
    if not cands and num:
        n = int(num.group(1))
        cands = [m.start() for m in re.finditer(rf"^\s*chapter\s+(?:{n}|{_roman(n)})\b", text, re.I | re.M)]
    at_line_start = lambda c: re.fullmatch(r"\s*(?:chapter\s+\w+[.:]?\s*)?", text[text.rfind("\n", 0, c) + 1:c], re.I)  # a heading, not the same words inside a sentence
    c = next((c for c in cands if c > max(text.find("\n"), 0) and at_line_start(c)), 0)  # a hit on the first line is the running page header
    if not c:
        return 0
    start = text.rfind("\n", 0, c) + 1
    prev = text.rfind("\n", 0, max(start - 1, 0)) + 1
    return prev if re.match(r"\s*chapter\b", text[prev:start], re.I) else start


def _strip_heading(text: str, title: str) -> str:
    """The heading is announced from the title, so a leading copy of it in the body ("CHAPTER I: Mr. S herlock Holmes") is dropped."""
    norm = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())
    tn, paras = norm(title), text.split("\n\n")
    while len(paras) > 1 and len(paras[0]) < 120 and (re.match(r"chapter\s+[\divxlc]+\b", paras[0], re.I) or (len(norm(paras[0])) >= 4 and norm(paras[0]) in tn)):
        paras.pop(0)
    text = "\n\n".join(paras)
    sq, idx = _squash(text)
    tail = _squash(re.split(r"\s*[—–:]\s*", title, maxsplit=1)[-1])[0]
    if len(tail) >= 4 and sq.startswith(tail):  # the title line ran into the first sentence ("What John Rance Had To Tell It was one...")
        text = text[idx[len(tail) - 1] + 1:].lstrip(" \n")
    return text


def split_by_outline(entries: list[tuple[str, int, tuple]], pages: list[str], drop: set[str] = frozenset()) -> list[dict]:
    """Bookmarks (title, 0-based page, ancestor titles) -> chapters, each tagged with the work/part it sits under.
    Front/back matter and near-empty divider pages are dropped; a bookmark that has children is a container, not a chapter."""
    container = {k for k, e in enumerate(entries[:-1]) if len(entries[k + 1][2]) > len(e[2])}
    # a container on the same page as its first child has no text of its own
    marks = [[p, 0, t, anc, k in container] for k, (t, p, anc) in enumerate(entries) if not (k in container and entries[k + 1][1] == p)]
    marks.sort(key=lambda m: m[0])
    for m in marks:
        m[1] = cut_offset(pages[m[0]], m[2]) if m[0] < len(pages) else 0
    for a, b in zip(marks, marks[1:]):
        if a[0] == b[0]:
            b[1] = max(b[1], a[1])
    out = []
    for k, (p, cut, t, anc, is_container) in enumerate(marks):
        if SKIP_RE.match(t.strip()) or any(SKIP_RE.match(a.strip()) for a in anc):
            continue
        q, qcut = (marks[k + 1][0], marks[k + 1][1]) if k + 1 < len(marks) else (len(pages), 0)
        parts = [pages[p][cut:qcut]] if q == p else [pages[p][cut:], *pages[p + 1:q], *([pages[q][:qcut]] if qcut else [])]
        title = re.sub(r"^(\d+):\s*", r"Chapter \1: ", t.strip())
        text = _strip_heading(reflow(parts, drop, title), title)
        if len(text) > (3000 if is_container else 200):  # a container keeps its text only if it is a real introduction
            out.append({"title": title, "part": " › ".join(a.strip() for a in anc), "text": text})
    return out


def _pdf(path: Path) -> list[dict]:
    from pypdf import PdfReader

    r = PdfReader(str(path))
    pages = [p.extract_text() or "" for p in r.pages]
    drop = running_junk(pages)
    entries = []

    def walk(o, anc=()):
        last = None
        for x in o:  # pypdf puts an entry's children in a list right after it
            if isinstance(x, list):
                walk(x, anc + (last,) if last else anc)
            else:
                last = (x.title or "").strip()
                entries.append((last, r.get_destination_page_number(x), anc))
    try:
        walk(r.outline)
    except Exception:  # broken outline: fall back to headings
        entries = []
    if entries and not any(t.lower().endswith(".pdf") for t, *_ in entries):  # "Page_12.pdf" = merged-scan junk, not chapters
        chapters = split_by_outline(entries, pages, drop)
        if len(chapters) >= 3:
            return chapters
    return _split_by_headings(reflow(pages, drop))


def guess_details(path: str | Path, name: str = "") -> dict:
    """{title, author} from file metadata, else from the file name ("Title - AUTHOR.pdf", "CamelCaseTitle.pdf"). Editable in the UI."""
    path, title, author = Path(path), "", ""
    try:
        if path.suffix.lower() == ".pdf":
            from pypdf import PdfReader
            m = PdfReader(str(path)).metadata
            title, author = (m.title or "").strip(), (m.author or "").strip()
        elif path.suffix.lower() == ".epub":
            from ebooklib import epub
            b = epub.read_epub(str(path), options={"ignore_ncx": True})
            title = (b.get_metadata("DC", "title") or [("", 0)])[0][0]
            author = (b.get_metadata("DC", "creator") or [("", 0)])[0][0]
    except Exception:
        pass
    if not title or title.lower().endswith((".pdf", ".indd")) or "binder" in title.lower():  # junk metadata
        stem = re.sub(r"(?<=[a-z])(?=[A-Z])|[_]+", " ", Path(name or path.name).stem)
        title, _, a = stem.partition(" - ")
        author = author or (a.title() if a.isupper() else a)
    return {"title": title.strip(), "author": author.strip()}


def extract_chapters(path: str | Path) -> list[dict]:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".epub":
        chapters = _epub(path)
    elif ext == ".pdf":
        chapters = _pdf(path)
    elif ext in (".txt", ".md"):
        chapters = _split_by_headings(path.read_text(errors="ignore"))
    else:
        raise ValueError(f"unsupported file type: {ext}")
    chapters = [c for c in chapters if c["text"]]
    if not chapters:
        raise ValueError("no text found (scanned PDF or DRM-protected file?)")
    return chapters
