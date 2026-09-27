"""Checks that need no LLM, browser or network: the reference example passes every stage's
own validator, and the validators actually reject what they claim to."""
import json
from pathlib import Path

import pytest

from pipeline import library, plan as plan_mod, stages, timeline

EX = Path(__file__).resolve().parent.parent / "examples" / "token_bucket"
load = lambda name: json.loads((EX / name).read_text(encoding="utf-8"))


def test_catalogs_parse_from_runtime():
    assert {"jar", "bucket", "counter", "server"} <= set(plan_mod.PROP_HEIGHTS)
    assert {"api", "database", "cache"} <= plan_mod.ICONS
    assert {"idle", "walk", "cheer"} <= plan_mod.POSES


def test_reference_script_and_storyboard_pass():
    script, sb = load("script.json"), load("storyboard.json")
    assert stages.check_script(script) == []
    sents = stages.split_sentences(stages.script_text(script))
    assert stages.check_storyboard(sb, len(sents)) == []


def test_reference_scenes_pass_and_match_storyboard():
    script, sb, plan = load("script.json"), load("storyboard.json"), load("plan.json")
    sents = stages.split_sentences(stages.script_text(script))
    for i, (scene, board) in enumerate(zip(plan["scenes"], sb["scenes"])):
        a, b = board["sentences"]
        board["narration"] = " ".join(sents[a:b + 1])
        assert board["narration"] == scene["narration"]
        prev = {x["id"] for x in plan["scenes"][i - 1]["actors"]} if i else set()
        assert stages.check_scene(scene, board, i, prev, i == len(sb["scenes"]) - 1) == [], scene["id"]
    plan_mod.validate(plan)


def test_script_checker_rejects_short_and_filler():
    bad = {"sections": [{"part": "hook", "text": "Basically, in this video we explain caching."}], "claims": []}
    problems = " ".join(stages.check_script(bad))
    assert "160-250" in problems and "basically" in problems and "recap" in problems


def test_storyboard_checker_rejects_gaps_and_monotony():
    sb = {"scenes": [{"sentences": [0, 1], "mood": "night", "shots": [1, 2]},
                     {"sentences": [3, 3], "mood": "night", "shots": [1, 2]},
                     {"sentences": [4, 5], "mood": "night", "shots": [1]}]}
    problems = " ".join(stages.check_storyboard(sb, 6))
    assert "must start at 2" in problems and "3 in a row" in problems


def test_scene_checker_rejects_slides_and_unknown_cues():
    board = {"narration": "A cache keeps hot data close to the app so reads are fast and cheap every time."}
    slide = {"actors": [{"id": "t", "type": "text", "text": "Caching", "at": [6, 5]}],
             "shots": [{"beats": [{"at": "banana", "do": "enter", "actor": "t"}]}]}
    problems = " ".join(stages.check_scene(slide, board, 0, set(), False))
    assert "2-4 shots" in problems and "nothing HAPPENS" in problems and "'banana'" in problems


def test_cue_phrases_match_hyphenated_tts_words():
    words = [{"text": "four", "norm": "four", "start": 1.0}, {"text": "twenty-nine", "norm": "twenty nine", "start": 1.3}]
    assert timeline.find_phrase(words, "four twenty-nine") == 0


def test_layouts_place_actors():
    scene = {"actors": [{"id": "a", "size": 2}, {"id": "b", "size": 2}], "layouts": [{"kind": "row", "actors": ["a", "b"], "x": 6, "y": 8, "gap": 1}]}
    plan_mod.apply_layouts(scene)
    assert scene["actors"][0]["at"] == [4.5, 8.0] and scene["actors"][1]["at"] == [7.5, 8.0]


def test_duplicate_topics_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "DB_PATH", tmp_path / "lib.sqlite")
    library.add("Rate limiting with the token bucket algorithm", keywords=["rate limiting", "token bucket", "429"])
    assert library.find_duplicate("How token bucket rate limiting works", [])
    assert library.find_duplicate("How DNS resolution works", ["dns", "resolver"]) is None
