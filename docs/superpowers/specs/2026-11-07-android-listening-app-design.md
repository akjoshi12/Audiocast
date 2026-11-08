# Android listening app (offline player + automatic wifi sync)

## Intent and why

The audiobook generator runs on the user's Mac and produces one MP3 per chapter (`data/<book_id>/chNN/chapter.mp3`). The user commutes by subway, often with no signal, and wants to listen on their Android phone. The phone app is a **player with its own complete local copy** of the books they choose. It never generates anything and never needs the PC or internet while listening. Whenever the phone joins the same wifi as the PC, it syncs by itself. No cloud, no Tailscale, no PC awake during listening.

Success: the user adds a book once; from then on, chapters appear on the phone by themselves after the PC generates them, play offline with an Apple Music-like feel, and resume exactly where they stopped.

## Goals

- Native Android app, dark theme only, Apple Music look (big cover art, one red accent `#fa243c`, mini player above a tab bar). Mockups were approved in the brainstorm session (`.superpowers/brainstorm/71091-1794073042/content/app-screens.html`): Library grid, Book page with chapter list, Now Playing.
- Fully automatic sync on home wifi: for each book the user has added, download every ready chapter not yet on the phone, pick up chapters generated later, and push listening positions back to the PC. No "sync" button needed.
- Complete offline playback from phone storage, including background playback with the screen off, lock-screen/notification controls and headphone buttons.
- Remembers position per chapter and resumes there.
- Player controls: play/pause, previous/next chapter, back 15 s, forward 30 s, speed 0.75x-2x, sleep timer, scrubber, chapter list.
- Library is **phone-local**: the user picks which PC books to put on the phone ("Add a book" tile lists the PC's books as of the last sync) and can remove any. Removing deletes only the phone's files; the PC is never changed by library choices.
- Pairing: one-time pairing by scanning a code/QR shown on the PC page; afterwards only the paired phone can use the sync interface.
- A Sync tab showing: connected to PC or not found, what is downloading, last sync time.

## Non-goals

- Creating books, picking voices, editing scripts, or generating audio on the phone.
- Sync over mobile data or over the internet; no accounts, no cloud, no Tailscale.
- Light theme, iOS, tablets-specific layouts beyond what Compose gives (the phone is a Samsung SM_F966W foldable; it should work folded and unfolded).
- Syncing the phone's library choices to the PC.

## Anti-goals (a failure even if it technically works)

- Anything that changes or deletes data on the PC because of something done on the phone (other than saving listening positions).
- Playback that needs the network, or that stops when the screen turns off.
- Re-downloading chapters that are unchanged, or filling the phone with books the user did not add.
- Sync that drains the battery in the background when not on home wifi.

## What the PC offers today (facts from the code)

- FastAPI app in `app/main.py`, run with `uvicorn app.main:app --host 127.0.0.1 --port 8000` (loopback only today).
- `GET /api/books` lists books; `data/<id>/meta.json` holds `title`, `author`; `data/<id>/chapters.json` is a list of `{title, part, text}`; chapters are addressed by 1-based index `n` (folder `ch{n:02d}`).
- `GET /api/books/{id}/chapters/{n}/audio` serves a chapter's audio. A chapter is "ready" when `data/<id>/chNN/chapter.mp3` exists. Chapters are re-rendered when scripts are edited, so the file can change.
- There are no cover images today.
- MP3s are ~35 MB per hour of audio (Holmes chapter 1: 10 MB for 17.5 min).

## Decisions made by the user

- Android phone connected over USB to the Mac; Android Studio, SDK (platforms 35 and 37.0, build-tools 34/36) are installed on the Mac, so the app can be built and installed directly.
- Everything automatic; library selection is manual and phone-local; books are added/removed whole, not chapter by chapter.
- Wifi sync with the PC while both are on the same network; no Tailscale / no always-on Mac.
- Paired access (not open to anyone on the wifi).
- Dark theme; Apple Music feel; the three mockup screens are approved.

## Calls made by Claude (not yet confirmed by the user)

- Stack: native Kotlin, Jetpack Compose UI, Media3 (ExoPlayer + MediaSession) for playback, Room/DataStore for the local library, WorkManager for sync.
- The phone discovers the PC on the LAN (mDNS/NSD service advertised by the PC) rather than the user typing an IP; the pairing QR also carries the PC's current address and a secret token.
- LAN exposure: the existing web app stays on loopback (it has create/render/edit endpoints and no auth). The phone talks to a separate, small, token-gated sync service on its own port that only serves the book list, chapter files and saved positions.
- Chapter identity: chapter numbers can shift when a book is re-split (this already happened with the Holmes book), so the phone stores each chapter with its number, title and version token and treats a changed title or token at a number as a different/changed chapter (re-download), never silently playing stale audio.
- If the PC is asleep or the app is not running, the phone just shows "PC not found" and retries when wifi reconnects; waking the Mac is out of scope.
- Pairing secret is a random token stored on both sides; every sync request carries it. LAN traffic is plain HTTP (home wifi, token-gated); TLS is out of scope.
- The PC must be running the app (server reachable on the LAN, not just loopback) at sync time; running it at login is a separate nicety, not required.
- Sync triggers when the phone connects to a wifi network where the PC is found (and periodically while on that wifi); it does nothing on mobile data.
- Chapter change detection by a version token (file size + modified time) returned by the PC; a changed chapter is re-downloaded and replaces the old file.
- Covers: generated on the phone as gradient tiles from the title (like the mockup) unless the book has a cover image; real covers are optional later.
- Listening positions: last-writer-wins per chapter, with the position from the phone saved on the PC in a small file per book; the PC web page does not use them yet.
- Skip back 15 s / forward 30 s, speeds 0.75-2x, "Add a book" list cached from the last sync so it works without the PC for browsing but downloading needs the PC.

## Left to the builder

- Exact PC endpoints and JSON shapes, as long as they are token-gated, read-only except for positions, and do not disturb the existing web app.
- Package/app name, icon, navigation details, animations, handling of storage-full and interrupted downloads (resume, no corrupt files).
- How the PC server is exposed to the LAN safely (binding, firewall prompt on macOS) and how pairing is shown in the existing web page.
- Testing approach, including how to verify on the connected phone (adb install, offline/airplane mode checks).
