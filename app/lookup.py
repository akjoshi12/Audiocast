"""Optional online lookup (Wikipedia, no key). Sends only a book title and author, never book text."""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://en.wikipedia.org/w/api.php"
STOP = {"the", "a", "an", "of", "and", "in", "on", "complete", "collection", "novel"}
CHARS_RE = re.compile(r"\n== *(?:main |principal |major |list of )?(?:characters|cast)[^=\n]*==\n(.*?)(?=\n== [^=])", re.I | re.S)


def _get(**params) -> dict:
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode({**params, 'format': 'json', 'formatversion': 2})}",
                                 headers={"User-Agent": "FullCastAudiobook/0.1 (local personal app)"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=10))
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        time.sleep(int(e.headers.get("Retry-After", 3)))  # ponytail: one polite retry; a lookup is once per book
        return json.load(urllib.request.urlopen(req, timeout=10))


def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower())) - STOP


MEDIA_RE = re.compile(r"\([^)]*\b(?:film|tv|television|series|album|song|band|video game|game|play|musical|opera|soundtrack|radio|miniseries|episode)\b[^)]*\)", re.I)


def find(title: str, author: str = "", get=_get) -> dict | None:
    """Best Wikipedia page for the book, or None. A page must share most words with the book title; film/TV/album pages of the
    same name lose to the book, and fewer extra words in the page title wins."""
    want = _words(title)
    if not want:
        return None
    hits = get(action="query", list="search", srsearch=f"{title} {author}".strip(), srlimit=8)["query"]["search"]
    ok = [h for h in hits if len(want & _words(h["title"])) / len(want) >= 0.6]
    if not ok:
        return None
    best = min(ok, key=lambda h: (bool(MEDIA_RE.search(h["title"])), len(_words(h["title"]) - want)))
    page = get(action="query", prop="extracts", explaintext=1, titles=best["title"])["query"]["pages"][0]
    text = page.get("extract", "")
    chars = CHARS_RE.search(text)
    return {"page": best["title"], "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(best["title"].replace(" ", "_")),
            "text": (re.split(r"\n== ", text, 1)[0][:1500] + ("\n\nCharacters:\n" + chars.group(1)[:5000] if chars else "")).strip()}
