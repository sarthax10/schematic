"""The library of videos this app has made (or reserved), used so the topic stage never
makes the same video twice. SQLite for the standalone pipeline; the future web app moves
this into Postgres like Antiquary's Story table.

Duplicate detection combines two signals, because either alone misses cases:
  - keyword overlap (always available): "token bucket rate limiting" vs "rate limiting
    with token buckets" share almost every content word;
  - embedding similarity (when an embedding model is available): catches paraphrases with
    different words ("throttling API clients" vs "rate limiting").

    python -m pipeline.library list
    python -m pipeline.library add "Rate limiting with a token bucket" --keywords rate,limiting,token,bucket,429
    python -m pipeline.library remove <slug>
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "library.sqlite"

KEYWORD_DUP = 0.6
EMBED_DUP = 0.86

STOP = set("a an the of in on for to and or with how why what is are does do your you it its vs versus using explained "
           "explain work works working intro introduction guide basics".split())


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def stem(w: str) -> str:
    """Crude suffix folding so limiter/limiting/limits and buckets/bucket compare equal."""
    for suf in ("ings", "ing", "ers", "er", "ions", "ion", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def terms(*texts: str) -> set[str]:
    out = set()
    for t in texts:
        for w in re.findall(r"[a-z0-9]+", t.lower()):
            if w in STOP or len(w) < 2:
                continue
            out.add(stem(w))
    return out


def cosine(a, b) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS videos (
        slug TEXT PRIMARY KEY, title TEXT, topic TEXT NOT NULL, category TEXT,
        keywords TEXT, summary TEXT, embedding TEXT, status TEXT NOT NULL,
        created_at REAL NOT NULL, out_dir TEXT)""")
    return db


def all_videos() -> list[dict]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM videos ORDER BY created_at DESC")]


def find_duplicate(topic: str, keywords: list[str], embedding: list[float] | None = None) -> tuple[dict, float, str] | None:
    """Returns (existing video, score, why) for the closest existing video over threshold."""
    mine = terms(topic, " ".join(keywords))
    best = None
    for v in all_videos():
        theirs = terms(v["topic"], v["title"] or "", " ".join(json.loads(v["keywords"] or "[]")))
        if slugify(topic) == v["slug"]:
            return v, 1.0, "same slug"
        # Overlap coefficient: how much of the smaller description the other one covers
        # (Jaccard is diluted when one side has a long keyword list). Needs 2+ shared
        # concepts, so a single common word like "api" never makes two topics "the same".
        shared = len(mine & theirs)
        kw = shared / min(len(mine), len(theirs)) if shared >= 2 and mine and theirs else 0.0
        emb = cosine(embedding, json.loads(v["embedding"])) if embedding and v["embedding"] else 0.0
        score, why = (kw, "keyword overlap") if kw / KEYWORD_DUP >= emb / EMBED_DUP else (emb, "meaning (embedding)")
        if (kw >= KEYWORD_DUP or emb >= EMBED_DUP) and (best is None or score > best[1]):
            best = (v, round(score, 3), why)
    return best


def add(topic: str, *, title: str = "", category: str = "", keywords: list[str] | None = None, summary: str = "",
        embedding: list[float] | None = None, status: str = "planned", out_dir: str = "") -> str:
    slug = slugify(title or topic)
    with connect() as db:
        db.execute(
            "INSERT OR REPLACE INTO videos VALUES (?,?,?,?,?,?,?,?,?,?)",
            (slug, title or topic, topic, category, json.dumps(keywords or []), summary,
             json.dumps(embedding) if embedding else None, status, time.time(), out_dir),
        )
    return slug


def set_status(slug: str, status: str, **fields) -> None:
    with connect() as db:
        db.execute("UPDATE videos SET status=? WHERE slug=?", (status, slug))
        for k, v in fields.items():
            if k in ("title", "out_dir", "summary"):
                db.execute(f"UPDATE videos SET {k}=? WHERE slug=?", (v, slug))


def remove(slug: str) -> None:
    with connect() as db:
        db.execute("DELETE FROM videos WHERE slug=?", (slug,))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    a = sub.add_parser("add")
    a.add_argument("topic")
    a.add_argument("--keywords", default="")
    a.add_argument("--category", default="")
    a.add_argument("--status", default="rendered")
    r = sub.add_parser("remove")
    r.add_argument("slug")
    args = ap.parse_args()
    if args.cmd == "list":
        for v in all_videos():
            print(f"{v['status']:>9}  {v['slug']:<45} {v['category'] or ''}")
    elif args.cmd == "add":
        print(add(args.topic, category=args.category, keywords=[k for k in args.keywords.split(",") if k], status=args.status))
    elif args.cmd == "remove":
        remove(args.slug)


if __name__ == "__main__":
    main()
