"""Mac side of the phone sync: library listing, versions, positions, token-gated HTTP."""
import json

import pytest

from app import sync


@pytest.fixture
def data(tmp_path, monkeypatch):
    b = tmp_path / "b1"
    (b / "ch01").mkdir(parents=True)
    (b / "meta.json").write_text(json.dumps({"name": "x.pdf", "title": "Book One", "author": "A. Writer"}))
    (b / "chapters.json").write_text(json.dumps([{"title": "One", "part": "P1", "text": "t"}, {"title": "Two", "part": "P1", "text": "t"}]))
    (b / "ch01" / "chapter.mp3").write_bytes(bytes(range(256)) * 4)
    (tmp_path / "stray").mkdir()  # a folder without chapters.json
    monkeypatch.setattr(sync, "DATA", tmp_path)
    return tmp_path


def test_library_marks_only_rendered_chapters_ready(data):
    [book] = sync.library()
    c1, c2 = book["chapters"]
    mp3 = data / "b1" / "ch01" / "chapter.mp3"
    assert (book["id"], book["title"], book["author"]) == ("b1", "Book One", "A. Writer")
    assert c1 == {"n": 1, "title": "One", "part": "P1", "ready": True, "size": 1024, "version": f"1024-{int(mp3.stat().st_mtime)}"}
    assert c2["ready"] is False and c2["version"] is None and c2["size"] is None and c2["n"] == 2


def test_library_skips_dirs_without_chapters_json(data):
    assert [b["id"] for b in sync.library()] == ["b1"]


def test_token_is_created_once_and_stable(data):
    t = sync.token()
    assert sync.token() == t and len(t) >= 32
    assert json.loads((data / "sync.json").read_text())["token"] == t


def test_positions_merge_keeps_newest_per_chapter(data):
    sync.merge_positions("b1", {"1": {"ms": 5000, "at": 100}})
    out = sync.merge_positions("b1", {"1": {"ms": 1, "at": 50}, "2": {"ms": 7, "at": 60}})
    assert out == {"1": {"ms": 5000, "at": 100}, "2": {"ms": 7, "at": 60}}
    assert sync.load_positions("b1") == out
    assert sync.merge_positions("b1", {"1": {"ms": 9000, "at": 200}})["1"]["ms"] == 9000


def test_chapter_audio_rejects_traversal_and_missing(data):
    assert sync.chapter_audio("b1", 1) == data / "b1" / "ch01" / "chapter.mp3"
    assert sync.chapter_audio("b1", 2) is None
    assert sync.chapter_audio("../b1", 1) is None and sync.chapter_audio("b1", 0) is None
    assert sync.chapter_audio("nope", 1) is None


# ---- HTTP service ----
from fastapi.testclient import TestClient  # noqa: E402

ROUTES = [("GET", "/sync/v1/library"), ("GET", "/sync/v1/books/b1/chapters/1/audio"),
          ("GET", "/sync/v1/positions/b1"), ("PUT", "/sync/v1/positions/b1")]


@pytest.fixture
def client(data):
    return TestClient(sync.sync_app), {"Authorization": f"Bearer {sync.token()}"}


@pytest.mark.parametrize("method,path", ROUTES)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic abc"}])
def test_all_routes_401_without_or_with_wrong_token(client, method, path, headers):
    c, _ = client
    r = c.request(method, path, headers=headers, json={})
    assert r.status_code == 401 and r.json() == {"detail": "bad token"}


def test_library_ok_with_token(client):
    c, h = client
    assert c.get("/sync/v1/library", headers=h).json()[0]["id"] == "b1"


def test_audio_range_returns_206_with_exact_bytes(client, data):
    c, h = client
    r = c.get("/sync/v1/books/b1/chapters/1/audio", headers={**h, "Range": "bytes=2-5"})
    assert r.status_code == 206 and r.content == bytes([2, 3, 4, 5]) and r.headers["content-range"] == "bytes 2-5/1024"
    assert r.headers["content-type"] == "audio/mpeg"


def test_audio_404_when_not_ready(client):
    c, h = client
    assert c.get("/sync/v1/books/b1/chapters/2/audio", headers=h).status_code == 404


def test_put_positions_roundtrip_and_merge(client):
    c, h = client
    assert c.put("/sync/v1/positions/b1", headers=h, json={"1": {"ms": 900, "at": 10}}).json() == {"1": {"ms": 900, "at": 10}}
    got = c.put("/sync/v1/positions/b1", headers=h, json={"1": {"ms": 1, "at": 5}, "2": {"ms": 2, "at": 6}}).json()
    assert got["1"]["ms"] == 900 and got["2"]["ms"] == 2
    assert c.get("/sync/v1/positions/b1", headers=h).json() == got


# ---- pairing ----
def test_pairing_url_has_host_port_token(data, monkeypatch):
    monkeypatch.setattr(sync, "lan_ip", lambda: "192.168.1.5")
    assert sync.pairing_url() == f"audiobook://pair?host=192.168.1.5&port=8001&token={sync.token()}"


def test_pairing_endpoint_returns_svg(data, monkeypatch):
    monkeypatch.setattr(sync, "lan_ip", lambda: "192.168.1.5")
    from app.main import app
    r = TestClient(app).get("/api/sync/pairing")
    assert r.status_code == 200 and r.json()["url"].startswith("audiobook://pair?") and r.json()["svg"].startswith("<svg")


def test_library_lists_cover_and_serves_it(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(sync, "DATA", tmp_path)
    d = tmp_path / "b1"; d.mkdir()
    (d / "chapters.json").write_text('[{"title": "One"}]')
    h = {"Authorization": f"Bearer {sync.token()}"}
    c = TestClient(sync.sync_app)
    assert c.get("/sync/v1/library", headers=h).json()[0]["cover"] is None
    assert c.get("/sync/v1/books/b1/cover", headers=h).status_code == 404
    (d / "cover.jpg").write_bytes(b"\xff\xd8\xff fake")
    assert c.get("/sync/v1/library", headers=h).json()[0]["cover"]
    r = c.get("/sync/v1/books/b1/cover", headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert c.get("/sync/v1/books/..%2Fx/cover", headers=h).status_code in (404, 422)
