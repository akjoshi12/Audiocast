# SPEC: Audiocast promo, storyline A "The Bennets"

GOAL: a stranger hears Mr. and Mrs. Bennet in two real voices, then sees the real app that made them and leaves knowing it runs on their own machine.
OUTPUT: HyperFrames, 1920x1080, 30 fps. TIME: 46.5 s = 1395 frames. No voiceover, no captions (the on-screen quotes are the book's text).

LOOK (flat colour fields, one per world, hard 14 px offset shadow, no gradients, no glow, 0% grain):
- Yellow #F2C230 (book world, reveal, end card), blue #1F4FD8 (the app), red #E8423A (the phone), ink #15130F (the numbers).
- Ink #15130F on yellow, white on blue/red, yellow on ink. Speaker colours: Mrs. Bennet red #E8423A, Mr. Bennet blue #1F4FD8, white text.
- Inter only: 900 for display (100-330 px, tracking -2%), 700 for the quotes (64 px), 400 for body (36-44 px). Min text 28 px.

OBJECTS: real screen recordings (`web-demo.mp4`, `phone-demo.mp4`) with 24 px radius and a hard ink shadow; real Ch. I audio (`bennets.wav`, 4 lines from the shipped render).

MOTION: wipes carry everything. Enter = clip-path wipe, power3.out, 12-18 frames. Quote text wipes left-to-right exactly over its audio duration. Scene changes: right-to-left wipe, bottom-up wipe, circle iris, left-to-right wipe (4 kinds). Nothing floats or loops.

SHOTS:
1. 0-11.6 s the four quotes wipe in as they are spoken; Mrs. left, Mr. right.
2. 11.6-16.9 s colours drain, "On the page, everyone sounds the same." then the wordmark.
3. 16.4-30.9 s web UI at 1.6x; the app's own four step labels, one at a time.
4. 30.4-37.2 s phone, "Then it plays on your phone."
5. 36.7-42.6 s two real numbers (97.6%, 97.0%) with their basis.
6. 42.2-46.5 s end card, wordmark wipe, "Runs entirely on your computer.", repo URL, hold 2.5 s.

BANNED: dark void as ground with small things, glow, gradients, cream paper + serif, small caps/mono labels, three cards, KPI grid, corner logo, floating loops, a claim not in EVAL.md/README.

QA: frame 0 (red tag block visible, not blank), 5 s, 12.5 s, 15.5 s, 24 s, 33 s, 40 s, 45 s.
