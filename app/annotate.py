"""Chapter text -> script lines (speaker, emotion, pause, mood) via LM Studio.

Text fidelity is structural: our code splits the text into numbered UNITS and the LLM only LABELS them
by id; it never copies or rewrites book text. Units are cut at quote marks, dash-dialogue, sentences and
paragraphs, but a unit is NOT assumed to be speech: the LLM decides (speech / thought / narration /
heading / text) because quotes are not always voices and voices are not always in quotes."""
import json
import re
from collections import Counter

from openai import OpenAI

LLM = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio", timeout=900)
MODEL = "qwen/qwen3.8-27b"
CHUNK_CHARS = 3000
LOAD = {"context": 64000, "parallel": 1, "ttl": 900}   # parallel 1 + 64k ctx + thinking off is what every shipped book was made with; 4 is far slower on this Mac
PRESET = __import__("pathlib").Path.home() / ".cache/lm-studio/config-presets/Resume Factory.preset.json"


def _preset() -> dict:
    """Request params from LM Studio's Resume Factory preset, read fresh every call; a missing preset is an error, never a silent fallback.
    Applied field by field: sending `preset` in the request makes LM Studio JIT-reload Qwen at parallel 4, undoing LOAD."""
    f = {x["key"]: x["value"] for x in json.loads(PRESET.read_text())["operation"]["fields"]}
    q = "ext.virtualModel.customField.qwen.qwen3.827b."
    effort = f.get(q + "reasoningEffort", "medium") if f.get(q + "enableThinking", False) else "none"   # "none" is how LM Studio's API turns Qwen thinking off
    return {"temperature": f["llm.prediction.temperature"], "extra_body": {"reasoning_effort": effort}}


def _chat(**kw):
    """Every Qwen call goes through here so the preset always wins."""
    return LLM.chat.completions.create(**kw, **_preset())


def ensure_loaded(model: str = MODEL) -> None:
    """Make sure LM Studio has `model` loaded with LOAD's settings (JIT loading would use its defaults). Silent no-op without the lms CLI."""
    import shutil
    import subprocess
    lms = shutil.which("lms") or "/usr/local/bin/lms"
    try:
        ps = json.loads(subprocess.run([lms, "ps", "--json"], capture_output=True, text=True, timeout=30).stdout or "[]")
        mine = [m for m in ps if m.get("identifier", "").split(":")[0] == model]   # LM Studio names extra copies "model:2"
        if len(mine) == 1 and mine[0]["identifier"] == model and mine[0].get("contextLength") == LOAD["context"] and mine[0].get("parallel") == LOAD["parallel"]:
            return
        for m in mine:   # reload from scratch so copies with other settings don't pile up (each is 16 GB)
            subprocess.run([lms, "unload", m["identifier"]], capture_output=True, timeout=60)
        subprocess.run([lms, "load", model, "-c", str(LOAD["context"]), "--parallel", str(LOAD["parallel"]), "--ttl", str(LOAD["ttl"]), "--identifier", model, "-y"],
                       capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass  # ponytail: LM Studio will still load it on demand with its own defaults
def unload_all() -> None:
    """Free every model LM Studio holds (called before voices start). Silent no-op without the lms CLI."""
    import shutil
    import subprocess
    try:
        subprocess.run([shutil.which("lms") or "/usr/local/bin/lms", "unload", "--all"], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        pass
KINDS = ["speech", "thought", "narration", "heading", "text"]

# double quotes (curly/straight) and single-quote speech (British style); apostrophes inside words never open a quote
QUOTE_RE = re.compile(r"(“[^”]*”|\"[^\"\n]*\"|(?<![\w’'])['‘][^'’]{2,}?['’](?!\w))")
DASH_RE = re.compile(r"^\s*[—–]\s*|^-\s+(?=\S)")
ABBR = ("Mr", "Mrs", "Ms", "Dr", "St", "Prof", "Sr", "Jr", "vs", "etc", "Capt", "Lt", "Col", "Gen", "No")
SENT_RE = re.compile(r"(?<=[.!?…])[\"”’')]*\s+(?=[A-Z“\"‘'(\[—])")

CHARS_SCHEMA = {
    "type": "object",
    "properties": {"characters": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "gender": {"enum": ["male", "female", "unknown"]},
            "age": {"enum": ["child", "young", "adult", "elderly"]},
            "voice": {"type": "string", "description": "short voice description"},
        }, "required": ["name", "gender", "age", "voice"]}}},
    "required": ["characters"],
}
# Forcing a JSON shape stops the (thinking) model from reasoning out loud, which doubled the tokens. Items are the compact lines.
LINES_SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "string"}}}, "required": ["lines"]}
CODES = {"N": "narration", "S": "speech", "T": "thought", "H": "heading", "X": "text"}

PROMPT = """You label the pieces ("units") of a book chapter for a full-cast audiobook.
Each unit has an id, a hint and its text. Hint QUOTED = it was inside quotation marks, DASH = it began with a
dash (dash dialogue), plain = no marks. [PARAGRAPH END] marks where a paragraph ends.
Hints are only hints. Quote marks do not always mean a character is speaking (scare quotes, titles, signs,
a word being discussed), and a character can speak with no marks at all (dash dialogue, oral-history
monologues, inner thoughts, letters, diaries, chat logs).

Reply with JSON {{"lines": [...]}} holding ONE string per unit, in order, and nothing else (no explanations):
  <id> <code> | <speaker> | <emotion> | <spoken part>
Codes: N narration (the narrator describing things, including dialogue tags like "she said"),
S speech (a character says it aloud), T thought (a character's inner thoughts),
H heading (chapter/section/person-name titles, date lines), X text (a letter, sign, document or message read out).
- For N and H write just `<id> N` or `<id> H`. Only if the narration should sound unusually tense, sad, etc.,
  add the emotion in the third field: `<id> N | | tense`.
- For S, T, X write the character: `<id> S | Elizabeth Bennet | sharp, amused`. One full name per character,
  consistently; found from context ("said Elizabeth", pronouns, who was just addressed, a monologue's named
  speaker). If the narrating "I" is a character, narration is still N. X with no clear author: speaker Narrator.
- In a story told as "I", only the narrator's OWN words get the narrator's name; every other person who speaks gets their own
  name (from tags like "said Stamford", "returned my companion", "he said", or who was just addressed). A reply to a
  question is spoken by someone else. Never credit another person's words to the narrator.
- emotion: a few words from the story context (e.g. "furious, voice shaking"; thoughts are "quiet, inward"). It describes how the
  CHARACTER sounds: when a dialogue tag names the manner ("he said angrily", "she whispered"), put that feeling on the quote's S line, never on the tag's N line.
- spoken part: only for an S/T unit whose text ENDS with a dialogue tag that is not spoken (e.g. "Out, he said."):
  copy the exact leading words that ARE spoken ("Out,"). Never change a word. Otherwise leave it out.
- End the line with ` ?` if you are guessing the speaker or code (a human will check those lines).
- End the line with ` ~` for a dramatic pause or a scene change after this unit.
Music mood: before the first unit, and whenever the mood of the scene changes, write a line
  MOOD: <word>
(tense, calm, melancholy, joyful, ominous, romantic, epic, mysterious, sorrowful, hopeful, playful, somber).
Every passage has a mood, even dry explanation or a quiet conversation (use calm). Never write none, and always
start with a MOOD line. The mood stays until the next MOOD line.
Current mood at the start of this chunk: {mood}
Known characters: {known}
{carry}"""


def _protect(s: str) -> str:
    for a in ABBR:
        s = re.sub(rf"\b{a}\.\s", f"{a}\u0001 ", s)
    return s


def units(text: str) -> list[dict]:
    """Deterministic split into {id, text, hint, para_end}. Only quote marks / leading dashes are stripped."""
    out = []
    for para in (p.strip() for p in text.split("\n\n") if p.strip()):
        if DASH_RE.match(para):
            parts = [(DASH_RE.sub("", para, count=1), "DASH")]
        else:
            parts = []
            for piece in QUOTE_RE.split(para):
                piece = piece.strip()
                if not piece:
                    continue
                if QUOTE_RE.fullmatch(piece):
                    parts.append((piece[1:-1].strip(), "QUOTED"))
                else:
                    parts += [(s, "") for s in SENT_RE.split(_protect(piece))]
        n0 = len(out)
        for t, hint in parts:
            t = t.replace("\u0001", ".").strip()
            if t.strip("“”\"‘’' —–-"):
                out.append({"text": t, "hint": hint, "para_end": False})
        if len(out) > n0:
            out[-1]["para_end"] = True
    for i, u in enumerate(out):
        u["id"] = i
    return out


def chunk(us: list[dict], size: int = CHUNK_CHARS) -> list[list[dict]]:
    out, cur, n = [], [], 0
    for u in us:
        if cur and n + len(u["text"]) > size and cur[-1]["para_end"]:
            out.append(cur); cur, n = [], 0
        cur.append(u); n += len(u["text"])
    return out + ([cur] if cur else [])


def _listing(us: list[dict]) -> str:
    return "\n".join(f'[{u["id"]}] ({u["hint"] or "plain"}) {u["text"]}' + (" [PARAGRAPH END]" if u["para_end"] else "")
                     for u in us)


LINE_RE = re.compile(r"^\s*\[?(\d+)\]?[.:)]?\s+([NSTHX])\b(.*)$")


MOODS = ["calm", "tense", "melancholy", "joyful", "ominous", "romantic", "epic", "mysterious", "sorrowful", "hopeful", "playful", "somber"]
MOOD_SCHEMA = {"type": "object", "properties": {"mood": {"type": "string", "enum": MOODS}}, "required": ["mood"]}


def pick_mood(text: str, model: str) -> str:
    """One forced-choice call (cannot answer "none"): the closest music mood for a passage."""
    try:
        r = _chat(
            model=model,
            messages=[{"role": "system", "content": "Pick the one mood that best fits this passage as background music for an audiobook."},
                      {"role": "user", "content": text}],
            response_format={"type": "json_schema", "json_schema": {"name": "mood", "schema": MOOD_SCHEMA}})
        m = r.choices[0].message
        return json.loads(m.content or getattr(m, "reasoning_content", None) or "")["mood"]
    except Exception:  # LLM hiccup must not lose the chapter
        return "calm"


def fill_moods(us: list[dict], text: str, model: str, pick=pick_mood) -> None:
    """Story units always get a real mood; headings stay "none". If the labeller gave a chunk one mood or none (it tends to write
    one MOOD line and never change it), a dedicated forced-choice call decides the chunk's mood; if it did change moods, keep its
    choices and let "none" gaps take the next real mood."""
    story = [u for u in us if u["kind"] != "heading"]
    if story and len({u["mood"] for u in story}) <= 1:
        m = pick(text[:2500], model)
        for u in story:
            u["mood"] = m
        return
    nxt = next((u["mood"] for u in story if u["mood"] not in ("none", "")), "calm")
    for u in story:
        if u["mood"] in ("none", ""):
            u["mood"] = nxt
        else:
            nxt = u["mood"]


def parse_labels(reply: str, us: list[dict], mood: str) -> list[dict] | None:
    """Parse the compact reply. Returns one label per unit, or None if any unit is missing."""
    by_id, cur = {}, mood
    for raw in reply.splitlines():
        raw = raw.strip()
        if raw.upper().startswith("MOOD:"):
            cur = raw[5:].strip().strip("[]*").lower() or cur
            continue
        m = LINE_RE.match(raw)
        if not m:
            continue
        i, code, rest = int(m.group(1)), m.group(2), m.group(3).strip()
        flags = ""
        while rest and rest[-1] in "?~":
            flags += rest[-1]; rest = rest[:-1].rstrip()
        f = [x.strip() for x in rest.lstrip("|").split("|")] if rest else []
        speaker = emotion = spoken = ""
        if code in "STX":
            speaker, emotion, spoken = (f + ["", "", ""])[:3]
        else:
            emotion = (f + ["", ""])[1] if len(f) > 1 else ""
        by_id[i] = {"id": i, "code": code, "speaker": speaker, "emotion": emotion, "spoken_part": spoken,
                    "unsure": "?" in flags, "beat": "~" in flags, "mood": cur}
    if {u["id"] for u in us} - by_id.keys():
        return None
    out = []
    for u in us:
        l = by_id[u["id"]]
        kind = CODES[l["code"]]
        voiced = kind in ("speech", "thought") or (kind == "text" and l["speaker"] and l["speaker"] != "Narrator")
        speaker = l["speaker"] if voiced else "Narrator"
        if voiced and not speaker:
            speaker, l["unsure"] = "Narrator", True
        emotion = l["emotion"] or ("quiet, inward" if kind == "thought" else "calm")
        pause = 1.5 if (l["beat"] or kind == "heading") else 0.7 if u["para_end"] else 0.3
        out.append({"id": u["id"], "kind": kind, "speaker": speaker, "emotion": emotion, "pause_after": pause,
                    "mood": "none" if kind == "heading" else l["mood"], "unsure": l["unsure"],
                    "spoken_part": l["spoken_part"]})
    return out


def label_chunk(us: list[dict], known: dict, carry: str, mood: str, model: str, retries: int = 3) -> list[dict]:
    for _ in range(retries):
        r = _chat(
            model=model,
            messages=[{"role": "system", "content": PROMPT.format(known=", ".join(known) or "none", carry=carry, mood=mood)},
                      {"role": "user", "content": _listing(us)}],
            response_format={"type": "json_schema", "json_schema": {"name": "lines", "schema": LINES_SCHEMA}})
        m = r.choices[0].message
        try:
            reply = "\n".join(json.loads(m.content or getattr(m, "reasoning_content", None) or "")["lines"])
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        labels = parse_labels(reply, us, mood)
        if labels:
            return labels
    # never kill a whole book over one chunk: fall back to the narrator and ask for human review
    return [{"id": u["id"], "kind": "narration", "speaker": "Narrator", "emotion": "calm", "pause_after": 0.4,
             "mood": mood, "unsure": True, "spoken_part": ""} for u in us]


def describe(names: list[str], sample: str, model: str, about: str = "") -> list[dict]:
    """One small call: gender / age group / voice description for newly seen characters."""
    r = _chat(
        model=model,
        messages=[{"role": "system", "content": "From the book excerpt, give gender, age group and a short description of the speaking VOICE (pitch, timbre, pace, accent; never the mood of the scene) for each listed character. If the excerpt does not tell, use the book background below if there is one (the excerpt wins if they disagree), else make the best guess from the name."},
                  {"role": "user", "content": f"{about}Characters: {', '.join(names)}\n\nExcerpt:\n{sample}"}],
        response_format={"type": "json_schema", "json_schema": {"name": "chars", "schema": CHARS_SCHEMA}})
    m = r.choices[0].message
    try:
        got = {c["name"]: c for c in json.loads(m.content or getattr(m, "reasoning_content", None) or "")["characters"]}
    except (json.JSONDecodeError, KeyError):
        got = {}
    return [got.get(n, {"name": n, "gender": "unknown", "age": "adult", "voice": ""}) for n in names]


def _split_tags(us: list[dict]) -> list[dict]:
    """Cut a trailing dialogue tag off a speech unit when the LLM named the spoken part and it really is the start."""
    out = []
    for u in us:
        sp = (u.pop("spoken_part", "") or "").strip()
        # transcript-style "Name: words" -- the label is formatting, not speech (ponytail: only when it names this speaker)
        m = re.match(r"([A-Z][\w. ]{1,30}):\s+", u["text"])
        if m and u["kind"] == "speech" and m.group(1).split()[0].lower() in u["speaker"].lower():
            u["text"] = u["text"][m.end():]
            sp = sp[m.end():] if sp.startswith(m.group(0)) else sp
        if sp and u["kind"] in ("speech", "thought") and u["text"].startswith(sp) and len(u["text"]) - len(sp) > 3:
            rest = u["text"][len(sp):].strip(" ,")
            out.append({**u, "text": sp, "para_end": False, "pause_after": 0.15})
            out.append({**u, "text": rest, "kind": "narration", "speaker": "Narrator", "emotion": "calm"})
        else:
            out.append(u)
    return out


TAG_VERBS = re.compile(r"\b(said|says|asked|replied|answered|cried|remarked|returned|added|exclaimed|whispered|shouted|murmured|"
                       r"observed|continued|called|muttered|inquired|suggested|declared|laughed|ejaculated|interrupted|went on|"
                       r"snapped|growled|hissed|screamed|yelled|sobbed|shrieked|roared|bellowed|sighed|groaned|stammered|demanded|begged|pleaded|warned)\b", re.I)


def fix_tags(us: list[dict]) -> None:
    """A short unquoted fragment right after a quote in the same paragraph that holds a speech verb ("I answered.") is a dialogue
    tag: always the narrator's, and the quote before it flows into it (short pause) instead of a sentence-end gap.
    ponytail: verb list + length cap; an unusual tag verb stays as the LLM labelled it."""
    for prev, u in zip(us, us[1:]):
        if (u["hint"] == "" and prev["hint"] == "QUOTED" and not prev["para_end"] and len(u["text"]) <= 80
                and TAG_VERBS.search(u["text"])):
            u.update(kind="narration", speaker="Narrator", emotion="calm")
            if prev["kind"] in ("speech", "thought"):
                prev["pause_after"] = min(prev["pause_after"], 0.15)


# ponytail: -ly words that are not manners; a new false cue means adding it here (a real fix needs a POS tagger)
NOT_MANNER = {"only", "early", "finally", "suddenly", "family", "reply", "really", "nearly", "immediately", "presently", "directly", "simply", "merely",
              "hardly", "lately", "shortly", "usually", "certainly", "probably", "actually", "likely", "lovely", "lonely", "apply", "supply",
              "italy", "july", "belly", "jelly", "silly", "holy", "ugly", "rely", "fly", "eventually", "obviously", "apparently", "recently", "exactly", "elderly", "highly", "considerably", "slightly", "truly"}
VERB_CUE = {v: c for vs, c in (("shouted yelled screamed roared bellowed shrieked", "shouting"), ("whispered", "whispering"),
            ("murmured muttered", "muttering, low"), ("cried exclaimed", "exclaiming"), ("snapped growled hissed", "sharp, angry"),
            ("sobbed", "sobbing"), ("sighed groaned", "weary"), ("stammered", "stammering, nervous"), ("pleaded begged", "pleading")) for v in vs.split()}
OPEN = ("", "calm", "quiet, inward")   # emotions the labeller left unset: a manner in the tag may fill these, a real one wins


def _manner(t: str) -> str | None:
    """How a tag says it: an -ly adverb near the verb (next 4 words, or the one before; names are capitalised so skipped; "faintly smiling"
    is a participle phrase, not a manner), else an expressive verb's direction, else None. ponytail: word-window heuristic, no parsing."""
    m = TAG_VERBS.search(t)
    pre, post = re.findall(r"[A-Za-z']+", t[:m.start()]), re.findall(r"[A-Za-z']+", t[m.end():])
    ws = pre[-1:] + post
    for n in range(len(pre[-1:]) + min(4, len(post))):
        w, nxt = ws[n], (ws[n + 1] if n + 1 < len(ws) else "")
        if w.endswith("ly") and w.islower() and len(w) > 4 and w not in NOT_MANNER and not nxt.lower().endswith(("ing", "ed")):
            return w
    return VERB_CUE.get(m.group(1).lower())


def fix_emotions(us: list[dict]) -> None:
    """The feeling belongs to the quote, never the narrator's tag. A tag (short narration with a speech verb, next to a quote in the same
    paragraph) is calm, and a manner it names ("said angrily", "whispered") moves onto the quote unless the labeller already gave it a
    real emotion. All other narration keeps its emotion. ponytail: tags are <=80-char units; a long sentence holding a tag is left alone."""
    for i, u in enumerate(us):
        if u["kind"] != "narration" or len(u["text"]) > 80 or not TAG_VERBS.search(u["text"]):
            continue
        q = lambda n: us[n] if 0 <= n < len(us) and us[n]["kind"] in ("speech", "thought") else None
        before = q(i - 1) if i and not us[i - 1]["para_end"] else None
        after = q(i + 1) if not u["para_end"] else None
        if not (before or after):
            continue
        u["emotion"] = "calm"
        cue = _manner(u["text"])
        if not cue:
            continue
        if before and before["emotion"] in OPEN:
            before["emotion"] = cue
            if after and after["speaker"] == before["speaker"] and after["emotion"] in OPEN:
                after["emotion"] = cue
        elif not before and after and after["emotion"] in OPEN:
            after["emotion"] = cue


_V = TAG_VERBS.pattern.replace("(", "(?:", 1)   # non-capturing, so the name groups below are 1 and 2
NAME_TAG = re.compile(rf"{_V}\s+(?:[a-z]+\s+)?([A-Z][a-z]+)\b|\b([A-Z][a-z]+)\s+{_V}")
NOT_NAMES = {"He", "She", "They", "We", "It", "You", "Then", "There", "But", "And", "So", "Yes", "No"}


def _tag_name(t: str) -> str | None:
    """"said Stamford, introducing us" / "Stamford said" -> Stamford (a capitalised word next to a speech verb)."""
    for m in NAME_TAG.finditer(t):
        n = m.group(1) or m.group(2)
        if n and n not in NOT_NAMES:
            return n
    return None


def fix_turns(us: list[dict]) -> None:
    """First-person books ("I said", "remarked my companion"): the labeller tends to credit every quote of a conversation to the
    narrating "I". Tags decide instead: "I asked" / "said I" = the narrator, a name next to a speech verb = that person, "he said" /
    "my companion" = the other. A quote with no tag is a new turn (the other voice) when it follows another quote, a paragraph break,
    or a question; after a tag it continues the same speaker when it starts lowercase or the quote before ended with a comma.
    Only runs when the "I" is identifiable (3+ quotes tagged "I <verb>"). A quote the labeller gave to a third person stays unless a
    tag names someone else. ponytail: two-voice conversations; the other person is the nearest tag that names someone."""
    is_tag = lambda u: u["kind"] == "narration" and len(u["text"]) <= 140 and TAG_VERBS.search(" ".join(u["text"].split()[:6]))
    is_me = lambda t: re.search(rf"\bI\s+{_V}|{_V}\s+I\b", t)
    # turns: lists of speech units that one voice says, plus the tag texts that belong to them
    turns, last = [], None          # last = ("S"|"T"|"N", unit)
    for k, u in enumerate(us):
        if u["kind"] == "speech":
            new = True
            if last and last[0] == "T" and not last[1]["para_end"]:
                prev_q = turns[-1]["q"][-1]["text"].rstrip("\"”’' ") if turns and turns[-1]["q"] else ""
                new = not (u["text"][:1].islower() or prev_q.endswith(",") or not prev_q.endswith("?"))
            if new:
                turns.append({"q": [], "tags": [], "at": k})
            turns[-1]["q"].append(u)
            last = ("S", u)
        elif is_tag(u):
            if last and last[0] != "N" and turns:
                turns[-1]["tags"].append(u["text"])          # follows a quote: that quote's tag
            elif k + 1 < len(us) and us[k + 1]["kind"] == "speech":
                turns.append({"q": [], "tags": [u["text"]], "at": k})   # "Stamford said, “...”": tag first, quote next
            last = ("T", u)
        else:
            last = ("N", u)
    turns = [t for t in turns if t["q"] or t["tags"]]
    mine = Counter(u["speaker"] for t in turns if any(is_me(x) for x in t["tags"]) for u in t["q"])
    top = mine.most_common(1)
    if not top or top[0][1] < 3:
        return
    me_name = top[0][0]
    me = set(me_name.lower().replace(".", "").split())
    is_mine = lambda sp: sp == "Narrator" or bool(set(sp.lower().replace(".", "").split()) & me)
    known = {u["speaker"] for u in us if u["speaker"] != "Narrator"}
    canon = lambda n: next((k for k in known if n.lower() in k.lower().split()), n)   # "Sherlock" -> the labeller's "Sherlock Holmes"
    named = [(t["at"], canon(_tag_name(x))) for t in turns for x in t["tags"] if not is_me(x) and _tag_name(x) and not is_mine(_tag_name(x))]
    other_near = lambda at: min(named, key=lambda x: abs(x[0] - at))[1] if named else None
    prev_role, prev_at = None, -99
    for t in turns:
        if not t["q"]:
            continue
        role, evidence = None, False
        for x in t["tags"]:
            if is_me(x):
                role, evidence = "me", True
            elif _tag_name(x) and not is_mine(_tag_name(x)):
                role, evidence = canon(_tag_name(x)), True
            elif re.search(r"\b(he|she|they|companion|friend)\b", x, re.I):
                role = "other"
        if not evidence and not all(is_mine(u["speaker"]) for u in t["q"]):
            prev_role, prev_at = "other", t["at"]       # the labeller named a third person: keep it
            continue
        if role is None and prev_role and t["at"] - prev_at <= 6:
            role = "other" if prev_role == "me" else "me"      # a reply
        if role == "me":
            for u in t["q"]:
                u["speaker"] = me_name
        elif role:
            who = role if role != "other" else other_near(t["at"])
            for u in t["q"]:
                u["speaker"] = who or u["speaker"]
        prev_role, prev_at = (("me" if role == "me" else "other") if role else None), t["at"]


SFX_SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "integer"}, "sound": {"type": "string"}, "at": {"enum": ["start", "end"]}}, "required": ["id", "sound", "at"]}}}, "required": ["lines"]}


def mark_sfx(lines: list[dict], model: str, batch: int = 20, tick=None) -> None:
    """One call per ~20 lines: lines whose text names a sound the listener would hear (a knock, fingers tapping, a bark, hooves, a clock).
    Stored as l["sfx"] = [{prompt, at}]; the sound-effect model turns the prompt into a short clip. Figurative or silent mentions get none,
    and a failed call leaves the lines as they are."""
    for k in range(0, len(lines), batch):
        part = lines[k:k + batch]
        if tick:
            tick(k // batch)
        try:
            r = _chat(
                model=model,
                messages=[{"role": "system", "content": "You add sound effects to an audiobook. For each numbered line that names a clear, distinctive NOISE the listener "
                           "would hear in the scene, give one short English prompt for a sound-effect generator and whether the sound happens at the start of the "
                           "line or at the end of it. Good: knocking on a door, fingers drumming or tapping on a table, a dog barking, a horse's hooves, a bird, "
                           "a clock ticking or striking, a door slamming, a gunshot, thunder, rain, a violin or piano being played, a bell, a carriage on cobblestones. "
                           "Only noises the narration says are heard in the scene (tires screeching, bells, birdsong, traffic, a knock). Never: voices, laughing, crying, sighing, speech, touching, handshakes, small gestures, footsteps or movement without a loud noise, "
                           "metaphors, silence, or anything the text does not clearly say is heard. Be strict: a typical page has zero or one. "
                           "Return only the lines that qualify."},
                          {"role": "user", "content": "\n".join(f"[{k + j}] {l['text']}" for j, l in enumerate(part))}],
                response_format={"type": "json_schema", "json_schema": {"name": "sfx", "schema": SFX_SCHEMA}})
            m = r.choices[0].message
            got = json.loads(m.content or getattr(m, "reasoning_content", None) or "")["lines"]
        except Exception:
            continue
        for g in sorted(got, key=lambda g: g.get("id", -1)):
            i, sound = g.get("id", -1), (g.get("sound") or "").strip()
            if (k <= i < k + len(part) and 3 <= len(sound) <= 80 and lines[i].get("kind") not in ("speech", "thought")
                    and not (i and lines[i - 1].get("sfx"))):   # a sound named inside dialogue is talk about it; never two lines in a row
                lines[i]["sfx"] = [{"prompt": sound, "at": g.get("at") if g.get("at") in ("start", "end") else "start"}]


def merge(us: list[dict]) -> list[dict]:
    """Join consecutive labelled units that read as one continuous voice into single lines."""
    lines = []
    for u in us:
        prev = lines[-1] if lines else None
        if (prev and not prev["_para_end"] and prev["speaker"] == u["speaker"] and prev["kind"] == u["kind"]
                and prev["emotion"] == u["emotion"] and prev["mood"] == u["mood"]
                and len(prev["text"]) + len(u["text"]) < 700):
            prev["text"] += " " + u["text"]
            prev["pause_after"], prev["_para_end"] = u["pause_after"], u["para_end"]
            prev["unsure"] = prev["unsure"] or u["unsure"]
            continue
        lines.append({**{k: u[k] for k in ("kind", "speaker", "text", "emotion", "pause_after", "mood", "unsure")},
                      "_para_end": u["para_end"]})
    for l in lines:
        l.pop("_para_end")
    return lines


LABEL_W, SFX_W = 3, 1


def annotate_chapter(text: str, model: str = MODEL, progress=None, about: str = "") -> dict:
    """Returns {characters, units (one label per unit, for agreement checks), lines (merged, for rendering)}."""
    chars, labelled, carry, mood = {}, [], "", "none"
    parts = chunk(units(text))
    # Progress is weighted work: LABEL_W : SFX_W is the measured 32 s (one label call) : 10 s (one 20-line sfx batch) ratio, so the web ETA is honest.
    nb_est = -int(-0.55 * sum(len(p) for p in parts) // 20)   # 310 merged lines came from 586 units on the measured chapter
    total = LABEL_W * len(parts) + SFX_W * nb_est
    for k, part in enumerate(parts):
        labels = label_chunk(part, chars, carry, mood, model)
        n0 = len(labelled)
        for u, l in zip(part, labels):
            labelled.append({**u, **{x: l[x] for x in ("kind", "speaker", "emotion", "pause_after", "mood", "unsure", "spoken_part")}})
        labelled[n0:] = _split_tags(labelled[n0:])
        fix_tags(labelled[max(n0 - 1, 0):])
        fill_moods(labelled[n0:], " ".join(u["text"] for u in part), model)
        new = []
        for u in labelled[n0:]:
            if u["speaker"] != "Narrator" and u["speaker"] not in chars and u["speaker"] not in new:
                new.append(u["speaker"])
        if new:
            sample = " ".join(u["text"] for u in part)[:1500]
            for c in describe(new, sample, model, about):
                chars[c["name"]] = c
        mood = next((u["mood"] for u in reversed(labelled) if u["mood"] != "none"), "none")  # carry the last real mood, not a heading's "none"
        if progress:
            progress(LABEL_W * (k + 1), total)
        last = labelled[-1]
        carry = (f"The previous unit was labelled kind={last['kind']}, speaker={last['speaker']}. "
                 "If this chunk continues a monologue or scene, keep the same speaker.")
    fix_turns(labelled)
    fix_emotions(labelled)
    late = sorted({u["speaker"] for u in labelled if u["speaker"] != "Narrator"} - chars.keys())   # e.g. a name only a tag gave
    if late:
        for c in describe(late, " ".join(u["text"] for u in labelled if u["speaker"] in late)[:1500], model, about):
            chars[c["name"]] = c
    used = {u["speaker"] for u in labelled}
    lines = merge(labelled)
    nb = -(-len(lines) // 20)   # real sfx batch count; correct the total once
    done0, total = LABEL_W * len(parts), LABEL_W * len(parts) + SFX_W * nb
    if progress:
        progress(done0, total, "Spotting sound effects")
    mark_sfx(lines, model, tick=progress and (lambda i: progress(done0 + SFX_W * i, total, "Spotting sound effects")))
    if progress:
        progress(total, total, "Spotting sound effects")
    return {"characters": [c for n, c in chars.items() if n in used], "units": labelled, "lines": lines}


def agreement(a: list[dict], b: list[dict]) -> dict:
    """Compare two labelings of the same text. Disagreement is a proxy for hard or wrong lines."""
    assert [u["id"] for u in a] == [u["id"] for u in b]
    norm = lambda s: re.sub(r"[^a-z]", "", s.lower().split()[0]) if s.split() else ""
    voice = lambda u: "narrator" if u["kind"] in ("narration", "heading") or u["speaker"] == "Narrator" else norm(u["speaker"])
    diff = [i for i, (x, y) in enumerate(zip(a, b)) if voice(x) != voice(y)]
    return {"units": len(a), "disagree": len(diff), "rate": len(diff) / max(len(a), 1), "ids": diff}


_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def number_words(n: int) -> str:
    if n < 20: return _ONES[n]
    if n < 100: return _TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else "")
    if n < 1000: return f"{_ONES[n // 100]} hundred" + (f" {number_words(n % 100)}" if n % 100 else "")
    return str(n)


def frame(title: str, lines: list[dict], part: str = "") -> list[dict]:
    """Narrator announces the section before it and closes it after: 'Chapter three.' ... 'End of chapter three.'
    `part` ("Work › Part 1") is spoken first so a chapter played on its own says which book it is from."""
    title = re.sub(r"\b(\d{1,3})\b", lambda m: number_words(int(m.group())), title)  # TTS clips a bare "1"
    title = "Preface" if title.lower() in ("opening", "full text", "front matter") else title.strip()
    say = lambda t, pause: {"kind": "heading", "speaker": "Narrator", "text": t, "emotion": "calm, clear, announcing",
                            "pause_after": pause, "mood": "none", "unsure": False}
    end = re.split(r"\s*[:—–]\s*", title)[0]
    short = lambda x: x.split(":")[0].capitalize() if x.split(":")[0].isupper() else x.split(":")[0]  # "THE 1ST LAW: Make It Obvious" -> "The 1st law"
    head = ", ".join(x for x in [*map(short, part.split(" › ")), title] if x)
    return [say(f"{head}.", 1.5), *lines, say(f"End of {end[0].lower() + end[1:]}.", 3.0)]
