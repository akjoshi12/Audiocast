from ebooklib import epub
from fastapi.testclient import TestClient

from app import main
from app.books import extract_chapters

LOREM = "He said nothing for a long while, and then he spoke. " * 8


def make_epub(path):
    b = epub.EpubBook()
    b.set_identifier("t"); b.set_title("T"); b.set_language("en")
    chs = []
    for i in (1, 2):
        c = epub.EpubHtml(title=f"Chapter {i}", file_name=f"c{i}.xhtml", lang="en")
        c.content = f"<h1>Chapter {i}</h1><p>{LOREM}</p><p>“Hello,” she said.</p>"
        b.add_item(c); chs.append(c)
    b.add_item(epub.EpubNcx()); b.add_item(epub.EpubNav())
    b.spine = ["nav", *chs]
    epub.write_epub(str(path), b)


def test_epub_chapters(tmp_path):
    p = tmp_path / "b.epub"; make_epub(p)
    ch = extract_chapters(p)
    assert [c["title"] for c in ch] == ["Chapter 1", "Chapter 2"]
    assert "“Hello,” she said." in ch[0]["text"]


def test_txt_headings(tmp_path):
    p = tmp_path / "b.txt"
    p.write_text(f"Chapter 1\n{LOREM}\nChapter 2\n{LOREM}")
    assert [c["title"] for c in extract_chapters(p)] == ["Chapter 1", "Chapter 2"]


def test_upload_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA", tmp_path / "data")
    p = tmp_path / "b.epub"; make_epub(p)
    r = TestClient(main.app).post("/api/books", files={"file": ("b.epub", p.read_bytes())})
    assert r.status_code == 200 and len(r.json()["chapters"]) == 2
    bad = TestClient(main.app).post("/api/books", files={"file": ("x.docx", b"zz")})
    assert bad.status_code == 400
