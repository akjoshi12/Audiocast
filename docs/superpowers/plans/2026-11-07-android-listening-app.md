# Android Listening App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A native Android player that holds a complete offline copy of the user's chosen audiobooks and syncs them automatically, after one-time pairing, from the Mac whenever both are on the same wifi.

**Architecture:** The Mac gets a second, token-gated FastAPI service (`app/sync.py`, port 8001, bound to the LAN, advertised over mDNS) that only lists books, serves chapter MP3s with Range support and stores listening positions; the existing web app stays on loopback. The Android app (`android/`, Kotlin, Compose, Media3, Room, WorkManager) pairs by QR, discovers the Mac, diffs the catalogue against local files, downloads atomically, and plays from phone storage.

**Tech Stack:** Python 3.12 / FastAPI / uvicorn / `zeroconf` / `segno` (QR SVG) on the Mac; Kotlin 2.x, Jetpack Compose, Media3 (ExoPlayer + MediaSession), Room, DataStore, WorkManager, OkHttp + kotlinx.serialization, Google Code Scanner, JUnit + MockWebServer on Android.

**Spec:** `docs/superpowers/specs/2026-11-07-android-listening-app-design.md`

## Global Constraints

- Android only, dark theme only; accent `#fa243c`; mini player above a 3-tab bar (Library, Now Playing, Sync); approved mockup: `.superpowers/brainstorm/71091-1794073042/content/app-screens.html`.
- Phone is player-only: no generating, editing, voices or book creation on it.
- Wifi only: no sync on mobile data (WorkManager `NetworkType.UNMETERED`).
- Phone library choices are phone-local; the only data the phone writes to the PC is listening positions.
- The existing web app stays on `127.0.0.1:8000`; only the sync service listens on the LAN, every route requires `Authorization: Bearer <token>`.
- Library = whole books added/removed by the user; sync downloads every ready chapter of added books, nothing else.
- Skip back 15 s, forward 30 s, speeds 0.75x-2x, sleep timer, resume per chapter, lock-screen/headphone controls, playback with screen off.
- Chapter change detection by version token `"{size}-{int(mtime)}"`; chapter identity = (book id, number) plus title and version; a changed title or version re-downloads.
- Package `app.audiobooks.player`, minSdk 31, compileSdk/targetSdk 35. Device: Samsung SM_F966W (adb serial `RFGYC0LWDTJ`), foldable: must work folded and unfolded.
- `/Users/atrijoshi/Documents/audioproject` is not a git repository: there are no commit steps; the user decides about `git init`.
- Android Studio's JDK: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"`; SDK at `~/Library/Android/sdk`; adb at `/opt/homebrew/bin/adb`.
- In this environment a hook may redirect `gradle`/build commands to `ctx_execute`; run them there and print only the tail or error lines.
- Mac Python tests: `.venv/bin/python -m pytest` from the project root.

## Review Focus

1. The Mac's IP changes after pairing (DHCP): the phone must find the Mac again by mDNS instead of failing with the saved address. Pinned in Task 6.
2. A download is interrupted (airplane mode, app killed): no partial file may ever be playable or counted as downloaded; the next sync resumes or restarts it. Pinned in Task 7.
3. A chapter is re-rendered, or a re-split shifts numbering so chapter 3 is now a different chapter: the phone must replace the audio, never play stale audio under a new title. Pinned in Task 7.
4. Wrong, missing or revoked token: every PC route (including audio) returns 401 and the phone shows "re-pair needed" instead of retrying forever. Pinned in Tasks 2 and 7.
5. The book or chapter disappears from the PC: the phone keeps its copy and marks it "no longer on PC"; sync never deletes local audio. Pinned in Task 7.

---

## File Structure

Mac: `app/sync.py` (data + HTTP service + start), edits to `app/main.py` (startup hook, `GET /api/sync/pairing`) and `app/static/index.html` (Pair phone button + QR), `tests/test_sync.py`, `requirements` line additions (`zeroconf`, `segno`) in `.venv`.

Android `android/app/src/main/java/app/audiobooks/player/`: `data/` (Room entities, DAO, `PairingStore`), `net/` (`PcApi`, `Discovery`), `sync/` (`SyncEngine`, `SyncWorker`), `player/` (`PlaybackService`, `PlayerController`), `ui/` (theme, `CoverArt`, screens, `MainActivity`).

---

### Task 1: Mac library, versions and positions store

**Files:**
- Create: `app/sync.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Produces: `DATA: Path` (module attribute, patched in tests), `token() -> str`, `version_of(p: Path) -> str`, `library() -> list[dict]`, `chapter_audio(book_id: str, n: int) -> Path | None`, `load_positions(book_id: str) -> dict[str, dict]`, `merge_positions(book_id: str, incoming: dict[str, dict]) -> dict[str, dict]`.
- `library()` item: `{"id","title","author","chapters":[{"n":int,"title":str,"part":str,"ready":bool,"version":str|None,"size":int|None}]}`; chapter `n` is 1-based; ready = `DATA/<id>/ch{n:02d}/chapter.mp3` exists.
- Positions map: `{"<n>": {"ms": int, "at": int}}`, `at` = phone epoch ms; merge keeps the larger `at` per chapter; stored at `DATA/<id>/positions.json`.

- [ ] **Step 1: Write failing tests** in `tests/test_sync.py` with a `tmp_path` fixture that builds `data/b1/{meta.json,chapters.json,ch01/chapter.mp3}` (2 chapters, only ch01 rendered) and monkeypatches `app.sync.DATA`:
  `test_library_marks_only_rendered_chapters_ready` (ch1 `ready` True with `version == f"{size}-{int(mtime)}"`, ch2 `ready` False, `version` None); `test_library_skips_dirs_without_chapters_json`; `test_token_is_created_once_and_stable` (two calls equal, 32+ hex chars, file `DATA/sync.json`); `test_positions_merge_keeps_newest_per_chapter` (older `at` ignored, newer replaces, file persisted); `test_chapter_audio_rejects_traversal` (`chapter_audio("../x", 1)` and `n=0` return None).
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_sync.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** the Interfaces above in `app/sync.py`; titles/author from `meta.json` (`title` falls back to `name`), chapters from `chapters.json`; validate `book_id` is a plain directory name under `DATA`.
- [ ] **Step 4: Run** the same command → all PASS.

### Task 2: Mac token-gated sync HTTP service

**Files:**
- Modify: `app/sync.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Consumes: Task 1 functions.
- Produces: `sync_app: FastAPI` with `GET /sync/v1/library` → `library()`; `GET /sync/v1/books/{book_id}/chapters/{n}/audio` (`audio/mpeg`, honours `Range`, 404 if not ready); `GET /sync/v1/positions/{book_id}`; `PUT /sync/v1/positions/{book_id}` (body = positions map, returns merged map). Every route requires `Authorization: Bearer <token()>` else 401 `{"detail":"bad token"}`.

- [ ] **Step 1: Write failing tests** with `fastapi.testclient.TestClient(sync_app)`: `test_all_routes_401_without_or_with_wrong_token` (parametrized over the four routes incl. audio), `test_library_ok_with_token`, `test_audio_range_returns_206_with_exact_bytes` (`Range: bytes=2-5` on a known file → 206, body equals slice, `Content-Range` set), `test_audio_404_when_not_ready`, `test_put_positions_roundtrip_and_merge`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `sync_app` with a `Depends(require_token)` on an `APIRouter` (constant-time compare via `secrets.compare_digest`); audio via `FileResponse(path, media_type="audio/mpeg")` (Starlette 1.x handles Range).
- [ ] **Step 4: Run** → PASS.

### Task 3: Start service on the LAN, mDNS, pairing QR

**Files:**
- Modify: `app/sync.py` (add `start() -> None`, `lan_ip() -> str`, `pairing_url() -> str`), `app/main.py` (startup call, `GET /api/sync/pairing`), `app/static/index.html` (Pair phone button + inline SVG)
- Test: `tests/test_sync.py`

**Interfaces:**
- Produces: `pairing_url()` = `audiobook://pair?host=<lan_ip>&port=8001&token=<token>`; `start()` runs `uvicorn` for `sync_app` on `0.0.0.0:8001` in a daemon thread (idempotent) and registers mDNS service type `_audiobook._tcp.local.` named `AudioBook PC` on port 8001 with TXT `v=1`; `GET /api/sync/pairing` → `{"url": str, "svg": str}` (QR via `segno`, `svg` from `segno.make(url).svg_inline(scale=6, dark="#fff", light=None)`).
- Dependency step: `uv pip install --python .venv/bin/python zeroconf segno`.

- [ ] **Step 1: Install** the two packages; confirm `import zeroconf, segno`.
- [ ] **Step 2: Write failing tests:** `test_pairing_url_has_host_port_token` (monkeypatch `lan_ip` → `192.168.1.5`; assert exact string), `test_pairing_endpoint_returns_svg` (`TestClient(app).get("/api/sync/pairing")` → `url` starts with `audiobook://pair?`, `svg` startswith `<svg`).
- [ ] **Step 3: Run** → FAIL.
- [ ] **Step 4: Implement** `lan_ip` (UDP connect to `10.255.255.255`, read socket name, fallback `127.0.0.1`), `pairing_url`, `start`; in `app/main.py` call `sync.start()` from a FastAPI `startup` handler; add the endpoint; add a "Pair phone" button in `index.html` that fetches the endpoint and shows the SVG with the text "Scan with the AudioBooks app".
- [ ] **Step 5: Run** the tests → PASS. Then restart the server and verify from the Mac: `python3 -c "import urllib.request as u;print(u.urlopen('http://<lan_ip>:8001/sync/v1/library').read())"` raises HTTP 401, and with the token header returns JSON including Holmes. Expected: 401 then JSON. (macOS may show a firewall prompt: Allow.)

### Task 4: Android project scaffold, dark theme, navigation shell

**Files:**
- Create: `android/` Gradle project (version catalog, `app` module, wrapper), `ui/Theme.kt`, `ui/CoverArt.kt`, `MainActivity.kt`, placeholder screens
- Test: `android/app/src/test/.../CoverArtTest.kt`

**Interfaces:**
- Produces: `fun coverColors(title: String): Pair<Color, Color>` (deterministic from `title.hashCode()`, from a palette of 6 gradients matching the mockup), `@Composable fun Cover(title: String, modifier: Modifier)`, `@Composable fun AudiobooksTheme(content)` (background `#000000`, surface `#1C1C1E`, accent `#FA243C`, secondary text `#9A9AA1`), a 3-tab shell (Library, Now Playing, Sync) with a slot for the mini player.
- Tooling: `brew install gradle`, then `gradle wrapper --gradle-version 8.10.2` inside `android/`; plugins AGP 8.7.x, Kotlin 2.0.x with Compose compiler plugin; `local.properties` with `sdk.dir`.

- [ ] **Step 1: Write failing test** `coverColors_isDeterministicAndDiffersAcrossTitles` (same title → equal pairs; "A Study in Scarlet" vs "Atomic Habits" → different).
- [ ] **Step 2: Implement** scaffold + theme + shell; run `./gradlew :app:testDebugUnitTest` → PASS.
- [ ] **Step 3: Install** with `./gradlew :app:installDebug` and `adb -s RFGYC0LWDTJ shell am start -n app.audiobooks.player/.MainActivity`; verify by `adb shell screencap` pulled to the scratchpad that the app shows black background, red accent tab, three tabs. Expected: app launches without crash (`adb logcat -d | grep AndroidRuntime` empty).

### Task 5: Local data layer

**Files:**
- Create: `data/Entities.kt`, `data/LibraryDao.kt`, `data/AppDb.kt`, `data/PairingStore.kt`, `data/LibraryStore.kt`
- Test: `android/app/src/androidTest/.../LibraryStoreTest.kt` (Room in-memory, runs on the phone via `./gradlew connectedDebugAndroidTest`)

**Interfaces:**
- Produces entities: `Book(id: String, title: String, author: String, onPhone: Boolean, onPc: Boolean)`, `Chapter(bookId: String, n: Int, title: String, part: String, version: String?, localFile: String?, remoteReady: Boolean, onPc: Boolean, positionMs: Long, positionAt: Long)` primary key `(bookId, n)`.
- `interface LibraryStore` (the seam Task 7 fakes): `suspend fun applyCatalog(remote: List<RemoteBook>)` (upsert titles/flags, mark missing as `onPc=false`, never delete rows or files), `fun books(): Flow<List<BookWithProgress>>`, `fun chapters(bookId: String): Flow<List<Chapter>>`, `suspend fun setOnPhone(bookId: String, on: Boolean)`, `suspend fun markDownloaded(bookId: String, n: Int, file: String, version: String)`, `suspend fun clearDownloads(bookId: String): List<String>` (returns files to delete), `suspend fun savePosition(bookId: String, n: Int, ms: Long, at: Long)`, `suspend fun pendingWork(): List<Chapter>` (onPhone books, `remoteReady` and (`localFile == null` or `version != remoteVersion`)). `data class RemoteBook(id,title,author,chapters: List<RemoteChapter>)`, `RemoteChapter(n,title,part,ready,version: String?, size: Long?)`.
- `PairingStore`: `data class Pairing(host: String, port: Int, token: String)`, `val pairing: Flow<Pairing?>`, `suspend fun save(p: Pairing)`, `suspend fun clear()`.

- [ ] **Step 1: Write failing tests:** `applyCatalog_keepsLocalFileWhenChapterVanishesFromPc` (chapter downloaded, then absent from catalog → row kept, `onPc=false`, `localFile` intact), `pendingWork_includesChangedVersionAndTitleChange`, `pendingWork_ignoresBooksNotOnPhone`, `setOnPhone_false_clearDownloads_returnsFilesAndKeepsPositions`.
- [ ] **Step 2: Run** `./gradlew connectedDebugAndroidTest` → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.

### Task 6: PC client, pairing and discovery

**Files:**
- Create: `net/PcApi.kt`, `net/Discovery.kt`, `ui/PairScreen.kt`
- Test: `android/app/src/test/.../PcApiTest.kt` (MockWebServer), `DiscoveryTest.kt`

**Interfaces:**
- Produces: `class PcApi(baseUrl: String, token: String, client: OkHttpClient)` with `suspend fun library(): List<RemoteBook>`, `suspend fun download(bookId: String, n: Int, dest: File, resumeFrom: Long = 0)` (sends `Range`, appends to `dest`), `suspend fun positions(bookId: String): Map<Int, Position>`, `suspend fun putPositions(bookId: String, m: Map<Int, Position>)`; throws `BadTokenException` on 401, `PcUnreachable` on IO failure. `fun parsePairingUrl(s: String): Pairing?` for `audiobook://pair?host=&port=&token=`. `class Discovery(nsd: NsdSource)` with `suspend fun locate(saved: Pairing): Pairing?` = saved address if `GET /sync/v1/library` answers (2 s timeout), else the mDNS `_audiobook._tcp` result (same token), else null.
- Pair screen uses Google Code Scanner (`play-services-code-scanner`), saves via `PairingStore`.

- [ ] **Step 1: Write failing tests:** `library_parsesCatalogue`, `bad_token_throwsBadTokenException` (401), `download_resumesWithRangeHeader` (server asserts `Range: bytes=100-`), `parsePairingUrl_roundtrip_and_rejectsGarbage`, `locate_usesMdnsWhenSavedHostIsDead` (fake `NsdSource` returns `10.0.0.9:8001`, saved `192.168.1.5` unreachable → result host `10.0.0.9`), `locate_returnsNullWhenNothingAnswers`.
- [ ] **Step 2: Run** `./gradlew :app:testDebugUnitTest` → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.

### Task 7: Sync engine and worker

**Files:**
- Create: `sync/SyncEngine.kt`, `sync/SyncWorker.kt`
- Test: `android/app/src/test/.../SyncEngineTest.kt` (fake `PcApiLike` and fake `LibraryStore`, temp dir)

**Interfaces:**
- Consumes: `LibraryStore`, `PcApiLike` (the Task 6 `PcApi` methods as an interface), `Discovery`.
- Produces: `class SyncEngine(api: PcApiLike, store: LibraryStore, dir: File, now: () -> Long)` with `suspend fun syncOnce(): SyncResult`; `sealed interface SyncResult { Done(downloaded: Int); PcNotFound; NeedsRepair; StorageFull; Failed(msg: String) }`. Steps: `store.applyCatalog(api.library())`; for each `pendingWork()` item download to `<dir>/<bookId>/<n>.mp3.part`, `fsync`, rename to `<n>.mp3`, `markDownloaded`; delete a replaced old file only after the new one is in place; merge positions both ways (newest `at` wins).
- `SyncWorker`: `CoroutineWorker` that resolves `PcApi` via `Discovery.locate`, runs `SyncEngine`; scheduled `PeriodicWorkRequest` every 15 min with `NetworkType.UNMETERED`, plus a one-time request at app start and after pairing; exposes `SyncState` (`StateFlow`) with last result, current file, last sync time for the Sync tab.

- [ ] **Step 1: Write failing tests:** `downloads_readyChaptersOfAddedBooksOnly`; `interruptedDownload_leavesNoPlayableFile_andResumesNextSync` (api throws mid-stream after writing 100 bytes → no `<n>.mp3`, `.part` present, `localFile` still null; next call completes and file bytes equal full body); `versionChange_replacesAudio_andTitleChangeAtSameNumberRedownloads`; `chapterGoneFromPc_keepsLocalCopy_markedOffPc`; `badToken_returnsNeedsRepair_andDownloadsNothing`; `diskFull_returnsStorageFull_andKeepsExistingFiles` (api download throws `IOException("No space left")`); `positions_newestWins_bothDirections`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.

### Task 8: Playback service and controller

**Files:**
- Create: `player/PlaybackService.kt`, `player/PlayerController.kt`, `player/SleepTimer.kt`
- Test: `android/app/src/test/.../SleepTimerTest.kt`, instrumented `PlaybackTest.kt`

**Interfaces:**
- Produces: `PlaybackService : MediaSessionService` (ExoPlayer, audio focus, `setHandleAudioBecomingNoisy(true)`, foreground notification with media controls; custom commands back-15 / forward-30); `class PlayerController(context)` with `fun play(bookId: String, n: Int)` (queue = the book's downloaded chapters in order, starting at `n`, seeks to the saved `positionMs`), `fun toggle()`, `fun back15()`, `fun forward30()`, `fun next()`, `fun previous()`, `fun setSpeed(x: Float)` (clamped 0.75-2.0), `fun sleepIn(minutes: Int?)`, `val state: StateFlow<PlayerUiState(bookId, n, title, isPlaying, positionMs, durationMs, speed, sleepLeftMs)>`; position saved via `LibraryStore.savePosition` every 5 s while playing and on pause/stop/chapter change.
- `SleepTimer(scope, onExpire)` pure class: `start(minutes)`, `cancel()`, `leftMs`.

- [ ] **Step 1: Write failing tests:** `SleepTimerTest.expiresAfterDurationAndCancelsCleanly` (virtual time); instrumented `playsDownloadedFileOffline_andSavesPosition` (copy a short test mp3 into app storage, `play`, wait 3 s, `toggle`, assert saved `positionMs >= 2500`); `resumeSeeksToSavedPosition`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** unit + `connectedDebugAndroidTest` → PASS.

### Task 9: Library and Book screens

**Files:**
- Create: `ui/LibraryScreen.kt`, `ui/BookScreen.kt`, `ui/AddBookSheet.kt`
- Test: `android/app/src/androidTest/.../LibraryUiTest.kt` (Compose test rule)

**Interfaces:**
- Consumes: `LibraryStore.books()/chapters()/setOnPhone/clearDownloads`, `Cover`, `PlayerController.play`.
- Behaviour (per approved mockup): 2-column grid of books with `onPhone`, badge "↓ all" or "↓ k/n", an "Add a book" tile opening `AddBookSheet` listing books with `onPc && !onPhone` from the last catalogue (works offline, shows "Connect to your PC wifi to download" note); Book page: cover, title, author, Play (resumes the last chapter) and Remove (confirm dialog; deletes the book's files, keeps positions); chapter rows with ✓ downloaded, "waiting for PC" when `!remoteReady`, "no longer on PC" when `!onPc`.

- [ ] **Step 1: Write failing tests:** `addBook_putsItInLibrary_removeBook_deletesFiles` (fake store), `chapterRows_showWaitingForPcAndOffPcStates`, `libraryEmptyState_showsAddTile`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; install and screenshot against the mockup.

### Task 10: Now Playing, mini player, Sync tab

**Files:**
- Create: `ui/NowPlayingScreen.kt`, `ui/MiniPlayer.kt`, `ui/SyncScreen.kt`
- Test: `android/app/src/androidTest/.../PlayerUiTest.kt`

**Interfaces:**
- Consumes: `PlayerController.state` and actions, `SyncState`, `PairingStore`.
- Behaviour: Now Playing per mockup (large cover, title, scrubber with times, ⟲15 ⏮ ⏯ ⏭ 30⟳, speed chip cycling 0.75/1/1.25/1.5/1.75/2, sleep menu Off/15/30/45/60, chapters sheet); mini player visible on all tabs while a chapter is loaded, tap opens Now Playing; Sync tab shows "Connected to your PC" / "PC not found" / "Re-pair needed" (button to Pair screen), "Phone storage is full" (existing downloads untouched), current download with progress, last sync time, and a "Pair with PC" action when unpaired.

- [ ] **Step 1: Write failing tests:** `speedChip_cyclesThroughAllSpeeds`, `miniPlayer_hiddenUntilChapterLoaded_thenOpensNowPlaying`, `syncTab_showsRepairButtonOnBadToken`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.

### Task 11: End-to-end on the phone

**Files:** none new; findings go to `BUILD_LOG.md` under a new dated entry.

- [ ] **Step 1:** Restart the Mac server; open the web page, click "Pair phone". Install the app (`./gradlew :app:installDebug`), scan the QR from the Pair screen. Expected: Sync tab shows "Connected to your PC".
- [ ] **Step 2:** In the app, add "Sherlock Holmes Complete". Expected within one sync: chapter 1 (`ch01/chapter.mp3`, ~10 MB) appears with ✓; badge shows "↓ 1/118" or the current count of rendered chapters.
- [ ] **Step 3:** Turn on airplane mode (`adb shell cmd connectivity airplane-mode enable`), force-stop and reopen the app, play chapter 1 for 30 s, pause. Expected: audio plays, screen-off playback continues, lock-screen controls work, reopening resumes at the saved position.
- [ ] **Step 4:** Disable airplane mode, change the Mac's wifi address (toggle wifi) and wait one sync interval. Expected: the app re-finds the Mac (Review Focus 1) and the position reaches `data/<id>/positions.json`.
- [ ] **Step 5:** Remove the book on the phone. Expected: phone storage freed, PC `data/` unchanged apart from `positions.json`.
- [ ] **Step 6:** Fold and unfold the phone (or `adb shell wm size` to the inner-screen size) on Library, Book and Now Playing. Expected: no clipped controls or crashes, playback continues across the change.
- [ ] **Step 7:** Record results (including anything that failed) in `BUILD_LOG.md`.
