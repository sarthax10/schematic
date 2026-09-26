"""Scene plan: the structured contract between whoever writes a video (a human today, the
LLM writer next) and the runtime that animates it. Closed vocabularies throughout — an
unknown scene type is an error, an unknown icon/tone/action is repaired to a documented
default with a warning, so nothing unvalidated ever reaches the renderer.

Plan shape:
{
  "title": str, "voice": str?, "rate": str?,
  "scenes": [
    {"type": <SCENE_TYPES>, "narration": str, "heading": str?, "data": {...},
     "steps": [{"at": "<phrase from this scene's narration>", "action": ..., ...}]}
  ]
}
"""
from __future__ import annotations

import json
from pathlib import Path

SCENE_TYPES = {"title", "architecture", "code", "stat", "takeaway", "compare"}

ACTIONS = {
    "title": set(),
    "architecture": {"reveal", "highlight", "fail", "packet", "label"},
    "code": {"highlight"},
    "stat": {"bars"},
    "takeaway": {"reveal"},
    "compare": {"reveal"},
}

# Mirrors runtime/icons.js — keep the two in sync.
ICONS = {
    "client", "browser", "user", "server", "api", "database", "cache", "queue", "load_balancer",
    "cdn", "gateway", "worker", "storage", "lock", "function", "cloud", "search", "clock",
    "check", "alert", "info", "cross",
}
TONES = {"signal", "ok", "fail", "ink2"}

DEFAULT_VOICE = "en-US-AndrewNeural"
DEFAULT_RATE = "+6%"


class PlanError(ValueError):
    pass


def load(path: str | Path) -> tuple[dict, list[str]]:
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))


def validate(plan: dict) -> tuple[dict, list[str]]:
    """Returns (cleaned plan, warnings). Raises PlanError for anything not repairable."""
    warnings: list[str] = []
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise PlanError("plan has no scenes")

    out_scenes = []
    for i, raw in enumerate(scenes):
        where = f"scene {i + 1}"
        kind = raw.get("type")
        if kind not in SCENE_TYPES:
            raise PlanError(f"{where}: unknown type {kind!r} (expected one of {sorted(SCENE_TYPES)})")
        narration = (raw.get("narration") or "").strip()
        if not narration:
            raise PlanError(f"{where}: narration is empty")
        data = dict(raw.get("data") or {})

        if kind == "architecture":
            ids = set()
            for n in data.get("nodes", []):
                if n.get("kind") not in ICONS:
                    warnings.append(f"{where}: node {n.get('id')!r} kind {n.get('kind')!r} → 'server'")
                    n["kind"] = "server"
                ids.add(n.get("id"))
            if not ids:
                raise PlanError(f"{where}: architecture scene has no nodes")
            data["edges"] = [e for e in data.get("edges", []) if e.get("from") in ids and e.get("to") in ids]
        if kind == "title":
            data["icons"] = [x for x in data.get("icons", []) if x in ICONS][:4]
        if kind == "code" and not data.get("code"):
            raise PlanError(f"{where}: code scene has no code")

        steps = []
        for s in raw.get("steps", []):
            action = s.get("action")
            if action not in ACTIONS[kind]:
                warnings.append(f"{where}: dropped step with action {action!r} (not valid for {kind})")
                continue
            if "tone" in s and s["tone"] not in TONES:
                warnings.append(f"{where}: tone {s['tone']!r} → 'signal'")
                s["tone"] = "signal"
            if kind == "architecture" and action != "packet" and s.get("target") not in ids:
                warnings.append(f"{where}: dropped {action} step targeting unknown node {s.get('target')!r}")
                continue
            if action == "packet":
                s["path"] = [p for p in s.get("path", []) if p in ids]
                if len(s["path"]) < 2:
                    warnings.append(f"{where}: dropped packet step with fewer than 2 known nodes")
                    continue
            steps.append(s)

        out_scenes.append({
            "type": kind,
            "narration": narration,
            "heading": (raw.get("heading") or "").strip() or None,
            "data": data,
            "steps": steps,
        })

    return {
        "title": plan.get("title") or "Untitled",
        "voice": plan.get("voice") or DEFAULT_VOICE,
        "rate": plan.get("rate") or DEFAULT_RATE,
        "scenes": out_scenes,
    }, warnings
