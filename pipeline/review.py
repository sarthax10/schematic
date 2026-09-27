"""Human script review: the checkpoint between writing and the long visual stages.

A local model writes a structurally sound script but can't be trusted on facts (vague real-
world examples, confident mistakes the accuracy pass may miss). A person reads every script
before any storyboard, scene or render time is spent on it. make.py stops after the accuracy
review until this module records an approval for the exact script text.

    python -m pipeline.review                  # list scripts waiting for review
    python -m pipeline.review out/<slug>       # open the review page for one video

The page lets the reviewer edit sections, see what the accuracy pass flagged, hear the
narration, then either approve (optionally continuing the pipeline right away) or request
changes with notes (the model revises the current script; it comes back for review).

State lives in out/<slug>/approval.json:
    {"status": "approved", "script_sha": "...", "at": ..., "by": "..."}
    {"status": "changes_requested", "notes": [...], "at": ...}
An approval only counts for the exact script it was given for (script_sha), so editing the
script after approving puts it back into review.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import http.server
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import edge_tts

from . import library, plan as plan_mod, stages

ROOT = Path(__file__).resolve().parent.parent
UI = Path(__file__).resolve().parent / "review_ui"
FONTS = ROOT / "runtime" / "fonts"
WORDS_PER_SECOND = 2.75  # measured on the default voice and rate


# ---- state ---------------------------------------------------------------------------------
def script_sha(script: dict) -> str:
    body = json.dumps({"title": script.get("title"), "sections": [(s.get("part"), s.get("text")) for s in script.get("sections", [])]},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


def _read(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def state(out: Path) -> dict:
    return _read(out / "approval.json", {"status": "pending"})


def gate(out: Path, script: dict) -> str:
    """'approved' (for this exact script), 'changes_requested', or 'pending'."""
    s = state(out)
    if s.get("status") == "approved":
        return "approved" if s.get("script_sha") == script_sha(script) else "pending"
    return s.get("status", "pending")


def normalize_review(r: dict | None) -> dict:
    """review.json has had two shapes; the page only needs passes + unresolved."""
    if not r:
        return {"passes": [], "unresolved": []}
    if "passes" in r:
        return r
    passes = [p for p in (r.get("first_pass"), r.get("second_pass")) if p] or [r]
    unresolved = [i for i in passes[-1].get("issues", []) if i.get("severity") in ("high", "medium")]
    return {"passes": passes, "unresolved": unresolved}


def packet(out: Path) -> dict:
    script = _read(out / "script.json")
    text = stages.script_text(script)
    words = len(text.split())
    return {
        "slug": out.name,
        "topic": _read(out / "topic.json", {}),
        "script": script,
        "review": normalize_review(_read(out / "review.json")),
        "approval": state(out),
        "gate": gate(out, script),
        "words": words,
        "seconds": round(words / WORDS_PER_SECOND),
        "problems": stages.check_script(json.loads(json.dumps(script))),
        "has_storyboard": (out / "storyboard.json").exists(),
    }


# ---- actions ---------------------------------------------------------------------------------
def save(out: Path, title: str, sections: list[dict]) -> dict:
    script = _read(out / "script.json")
    script["title"] = title.strip() or script.get("title")
    by_part = {s["part"]: s for s in script["sections"]}
    for s in sections:
        if s.get("part") in by_part:
            by_part[s["part"]]["text"] = s.get("text", "")
    script = stages.fix_script(script)  # same spoken-text cleanup the writer gets
    script.pop("_warnings", None)
    (out / "script.json").write_text(json.dumps(script, indent=1, ensure_ascii=False), encoding="utf-8")
    return packet(out)


def approve(out: Path, by: str = "reviewer") -> dict:
    script = _read(out / "script.json")
    (out / "approval.json").write_text(json.dumps(
        {"status": "approved", "script_sha": script_sha(script), "at": time.time(), "by": by}, indent=1), encoding="utf-8")
    library.set_status(out.name, "approved", title=script.get("title", ""), out_dir=str(out))
    return packet(out)


def request_changes(out: Path, notes: list[str]) -> dict:
    notes = [n.strip() for n in notes if n and n.strip()]
    (out / "approval.json").write_text(json.dumps(
        {"status": "changes_requested", "notes": notes, "at": time.time()}, indent=1, ensure_ascii=False), encoding="utf-8")
    library.set_status(out.name, "changes_requested")
    return packet(out)


def listen(out: Path) -> Path:
    """The whole script as one narration clip, so the reviewer hears pacing and emphasis."""
    script = _read(out / "script.json")
    mp3 = out / "review_listen.mp3"

    async def run():
        comm = edge_tts.Communicate(stages.script_text(script), plan_mod.DEFAULT_VOICE, rate=plan_mod.DEFAULT_RATE)
        with mp3.open("wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])

    asyncio.run(run())
    return mp3


def continue_pipeline(out: Path) -> Path:
    """Starts `make --resume` for this video in the background, with this process's
    environment (so it uses the same LLM backend). Returns the log path."""
    log = out / "make.log"
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    with log.open("ab") as fh:
        subprocess.Popen([sys.executable, "-u", "-m", "pipeline.make", "--resume", str(out)], cwd=ROOT,
                         stdout=fh, stderr=subprocess.STDOUT, creationflags=flags, start_new_session=os.name != "nt")
    return log


def waiting() -> list[Path]:
    """Videos whose script exists but hasn't been approved for its current text."""
    found = []
    for d in sorted((ROOT / "out").glob("*/script.json")):
        out = d.parent
        if (out / "topic.json").exists() and gate(out, _read(d)) != "approved":
            found.append(out)
    return found


# ---- server ---------------------------------------------------------------------------------
def serve(out: Path, port: int = 8791) -> http.server.ThreadingHTTPServer:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self._send(200, (UI / "index.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/api/packet":
                return self._json(packet(out))
            if path == "/listen.mp3" and (out / "review_listen.mp3").exists():
                return self._send(200, (out / "review_listen.mp3").read_bytes(), "audio/mpeg")
            if path.startswith("/fonts/") and (FONTS / Path(path).name).exists():
                return self._send(200, (FONTS / Path(path).name).read_bytes(), "font/woff2")
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            path = self.path.split("?")[0]
            try:
                if path == "/api/save":
                    return self._json(save(out, body.get("title", ""), body.get("sections", [])))
                if path == "/api/approve":
                    if body.get("sections"):
                        save(out, body.get("title", ""), body["sections"])
                    p = approve(out, by=body.get("by") or "reviewer")
                    if body.get("continue"):
                        p["continued_log"] = str(continue_pipeline(out))
                    return self._json(p)
                if path == "/api/changes":
                    if body.get("sections"):
                        save(out, body.get("title", ""), body["sections"])
                    p = request_changes(out, body.get("notes", []))
                    if body.get("continue"):
                        p["continued_log"] = str(continue_pipeline(out))
                    return self._json(p)
                if path == "/api/listen":
                    listen(out)
                    return self._json({"url": f"/listen.mp3?v={int(time.time())}"})
            except Exception as e:  # surfaced in the page, not swallowed
                return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
            self._send(404, b"not found", "text/plain")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", nargs="?", type=Path)
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    if not args.out:
        items = waiting()
        if not items:
            print("No scripts are waiting for review.")
        for out in items:
            s = state(out)
            print(f"  {s.get('status', 'pending'):<18} {out.relative_to(ROOT)}")
        return 0
    if not (args.out / "script.json").exists():
        print(f"{args.out} has no script.json yet", file=sys.stderr)
        return 2
    serve(args.out, args.port)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Reviewing {args.out.name}: {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
