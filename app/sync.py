"""Phone sync: what the Android app may see of the library, behind a pairing token. Read-only except listening positions."""
import json
import secrets
import socket
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

DATA = Path(__file__).resolve().parent.parent / "data"


def token() -> str:
    f = DATA / "sync.json"
    if f.exists():
        return json.loads(f.read_text())["token"]
    t = secrets.token_hex(24)
    f.write_text(json.dumps({"token": t}))
    return t


def _book_dir(book_id: str) -> Path | None:
    """A real book folder directly under DATA, or None (blocks ../ and absolute paths)."""
    d = DATA / book_id
    return d if d.parent == DATA and (d / "chapters.json").exists() else None


def _mp3(d: Path, n: int) -> Path:
    return d / f"ch{n:02d}" / "chapter.mp3"


def version_of(p: Path) -> str:
    s = p.stat()
    return f"{s.st_size}-{int(s.st_mtime)}"


def cover_file(d: Path) -> Path | None:
    """The book's poster: one the user uploaded, else the first page of its PDF (rendered once with pdftoppm)."""
    if not list(d.glob("cover.*")) and (d / "source.pdf").exists():
        subprocess.run(["pdftoppm", "-jpeg", "-r", "70", "-f", "1", "-l", "1", "-singlefile", str(d / "source.pdf"), str(d / "cover")], capture_output=True)
    return next(iter(d.glob("cover.*")), None)


def library() -> list[dict]:
    out = []
    for cj in sorted(DATA.glob("*/chapters.json")):
        d = cj.parent
        meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
        chapters = []
        for n, c in enumerate(json.loads(cj.read_text()), 1):
            f = _mp3(d, n)
            ready = f.exists()
            chapters.append({"n": n, "title": c.get("title", ""), "part": c.get("part", ""), "ready": ready,
                             "version": version_of(f) if ready else None, "size": f.stat().st_size if ready else None})
        cover = cover_file(d)
        out.append({"id": d.name, "title": meta.get("title") or meta.get("name") or d.name, "author": meta.get("author", ""),
                    "cover": version_of(cover) if cover else None, "chapters": chapters})
    return out


def chapter_audio(book_id: str, n: int) -> Path | None:
    d = _book_dir(book_id)
    if d is None or n < 1:
        return None
    f = _mp3(d, n)
    return f if f.exists() else None


def load_positions(book_id: str) -> dict[str, dict]:
    d = _book_dir(book_id)
    f = d / "positions.json" if d else None
    return json.loads(f.read_text()) if f and f.exists() else {}


def merge_positions(book_id: str, incoming: dict[str, dict]) -> dict[str, dict]:
    """Newest `at` (phone epoch ms) wins per chapter."""
    d = _book_dir(book_id)
    if d is None:
        return {}
    cur = load_positions(book_id)
    for n, p in incoming.items():
        if n not in cur or p["at"] > cur[n]["at"]:
            cur[n] = {"ms": int(p["ms"]), "at": int(p["at"])}
    (d / "positions.json").write_text(json.dumps(cur))
    return cur


def require_token(authorization: str = Header(default="")) -> None:
    if not secrets.compare_digest(authorization, f"Bearer {token()}"):
        raise HTTPException(401, "bad token")


router = APIRouter(prefix="/sync/v1", dependencies=[Depends(require_token)])


@router.get("/library")
def _library():
    return library()


@router.get("/books/{book_id}/chapters/{n}/audio")
def _audio(book_id: str, n: int):
    f = chapter_audio(book_id, n)
    if f is None:
        raise HTTPException(404, "chapter not ready")
    return FileResponse(f, media_type="audio/mpeg")  # Starlette answers Range requests with 206


@router.get("/books/{book_id}/cover")
def _cover(book_id: str):
    d = _book_dir(book_id)
    f = cover_file(d) if d else None
    if f is None:
        raise HTTPException(404, "no cover")
    return FileResponse(f, media_type="image/png" if f.suffix == ".png" else "image/jpeg")


@router.get("/positions/{book_id}")
def _get_positions(book_id: str):
    return load_positions(book_id)


@router.put("/positions/{book_id}")
def _put_positions(book_id: str, incoming: dict[str, dict]):
    return merge_positions(book_id, incoming)


sync_app = FastAPI(title="AudioBook sync")
sync_app.include_router(router)


SYNC_PORT = 8001
_started = False


def lan_ip() -> str:
    """The address other devices on this wifi reach this computer at."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # UDP connect sends nothing; it only picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def pairing_url() -> str:
    return f"audiobook://pair?host={lan_ip()}&port={SYNC_PORT}&token={token()}"


def _advertise() -> None:
    from zeroconf import ServiceInfo, Zeroconf
    info = ServiceInfo("_audiobook._tcp.local.", "AudioBook PC._audiobook._tcp.local.", port=SYNC_PORT,
                       addresses=[socket.inet_aton(lan_ip())], properties={"v": "1"})
    Zeroconf().register_service(info)  # the Zeroconf object lives for the rest of the process


def start() -> None:
    """Serve sync_app on the LAN and announce it over mDNS (once per process). The web app itself stays on loopback."""
    global _started
    if _started:
        return
    _started = True
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(sync_app, host="0.0.0.0", port=SYNC_PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    threading.Thread(target=_advertise, daemon=True).start()  # not on the event loop: zeroconf's sync API refuses to run there
