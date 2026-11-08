# Graph Report - audioproject  (2026-11-07)

## Corpus Check
- Large corpus: 445 files · ~1,049,653 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 277 nodes · 514 edges · 11 communities (7 shown, 4 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 12 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- TTS & Voice Casting
- Script Annotation
- Web API & Jobs
- Phone Sync Service
- Book Parsing
- Lookup & Narrator Logic
- Music Beds

## God Nodes (most connected - your core abstractions)
1. `annotate_chapter()` - 14 edges
2. `reflow()` - 14 edges
3. `make_epub()` - 11 edges
4. `work()` - 10 edges
5. `_dir()` - 10 edges
6. `extract_chapters()` - 9 edges
7. `split_by_outline()` - 9 edges
8. `speak()` - 9 edges
9. `_book_cast()` - 8 edges
10. `frame()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `client()` --calls--> `token()`  [EXTRACTED]
  tests/test_sync.py → app/sync.py
- `test_cancel_stops_job()` --calls--> `_job()`  [EXTRACTED]
  tests/test_api.py → app/main.py
- `test_chapter_audio_rejects_traversal_and_missing()` --calls--> `chapter_audio()`  [EXTRACTED]
  tests/test_sync.py → app/sync.py
- `test_token_is_created_once_and_stable()` --calls--> `token()`  [EXTRACTED]
  tests/test_sync.py → app/sync.py
- `test_annotate_live_messy()` --calls--> `annotate_chapter()`  [EXTRACTED]
  tests/test_annotate.py → app/annotate.py

## Import Cycles
- None detected.

## Communities (11 total, 4 thin omitted)

### Community 0 - "TTS & Voice Casting"
Cohesion: 0.06
Nodes (25): auto_cast(), contrast(), design_voice(), exaggeration(), line_file(), model(), render(), slow() (+17 more)

### Community 1 - "Script Annotation"
Cohesion: 0.08
Nodes (31): agreement(), annotate_chapter(), chunk(), describe(), fill_moods(), fix_tags(), frame(), label_chunk() (+23 more)

### Community 2 - "Web API & Jobs"
Cohesion: 0.08
Nodes (33): guess_details(), About, _about(), _aliases(), analyze(), work(), _apply_aliases(), audio() (+25 more)

### Community 3 - "Phone Sync Service"
Cohesion: 0.08
Nodes (24): pairing(), _start_phone_sync(), _advertise(), _audio(), _book_dir(), chapter_audio(), _get_positions(), lan_ip() (+16 more)

### Community 4 - "Book Parsing"
Cohesion: 0.11
Nodes (22): cut_offset(), _epub(), extract_chapters(), _join_hyphen(), _pdf(), walk(), reflow(), _roman() (+14 more)

### Community 5 - "Lookup & Narrator Logic"
Cohesion: 0.11
Nodes (16): find(), _words(), first_person_narrator(), test_about_roundtrip_and_offline_error(), test_cancel_stops_job(), test_first_person_narrator_is_detected_and_voiced_as_narrator(), test_full_flow(), test_job_error_is_reported() (+8 more)

### Community 6 - "Music Beds"
Cohesion: 0.18
Nodes (12): work(), bed(), cues(), loop(), mix(), _musicgen(), prompt_for(), L() (+4 more)

## Knowledge Gaps
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `frame()` connect `Script Annotation` to `Web API & Jobs`, `Book Parsing`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `work()` (e.g. with `analyze()` and `annotate_tick()`) actually correct?**
  _`work()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `TTS & Voice Casting` be split into smaller, more focused modules?**
  _Cohesion score 0.061683599419448475 - nodes in this community are weakly interconnected._
- **Why does `_design()` connect `Web API & Jobs` to `TTS & Voice Casting`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Should `Script Annotation` be split into smaller, more focused modules?**
  _Cohesion score 0.0786308973172988 - nodes in this community are weakly interconnected._
- **Should `Web API & Jobs` be split into smaller, more focused modules?**
  _Cohesion score 0.08233117483811286 - nodes in this community are weakly interconnected._
- **Should `Phone Sync Service` be split into smaller, more focused modules?**
  _Cohesion score 0.07682926829268293 - nodes in this community are weakly interconnected._