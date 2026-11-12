#!/usr/bin/env bash
# Overnight: scripts for every chapter of both books, then audio for every chapter.
# Needs the server running on :8000. Safe to re-run: it only queues what's missing.
# Run:  caffeinate -dims scripts/overnight.sh   (keeps the Mac awake; log: overnight.log)
exec python3 - "$@" <<'PY' 2>&1 | tee -a overnight.log
import json, time, urllib.request, datetime
B = "http://localhost:8000/api"
BOOKS = {"ca3f6ba2": "Sherlock Holmes Complete", "4d2f0bb1": "The Intelligent Investor"}
def call(path, post=False):
    r = urllib.request.Request(B + path, method="POST" if post else "GET")
    return json.load(urllib.request.urlopen(r, timeout=60))
def log(m): print(datetime.datetime.now().strftime("%H:%M:%S"), m, flush=True)
def drain():
    while True:
        try: q = call("/queue")
        except Exception as e: log(f"server not answering ({e}); retrying"); time.sleep(30); continue
        if not q: return
        log(f"{len(q)} jobs left; running: " + next((f"{j['book_name']} ch{j['n']} {j['kind']}" for j in q if j['state'] == 'running'), "-"))
        time.sleep(120)
for kind in ("analyze", "render"):
    for _ in range(3):  # re-queue pass catches chapters that failed or got a script late
        for b, name in BOOKS.items():
            r = call(f"/books/{b}/queue/{kind}", post=True)
            log(f"{kind} {name}: queued {len(r['queued'])}")
        drain()
log("done")
PY
