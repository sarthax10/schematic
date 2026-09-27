"""Recipes: every recipe builds a valid scene from its sample slots, cues are repaired rather
than failing, and direct_scene wires choice + slots together (with a scripted fake model)."""
import json

import pytest

from pipeline import plan as plan_mod, recipes, stages


@pytest.mark.parametrize("name", list(recipes.RECIPES))
def test_every_recipe_sample_builds_a_valid_scene(name):
    narration, slots = recipes.RECIPES[name].sample
    scene, repaired = recipes.build_scene(name, json.loads(json.dumps(slots)), narration)
    scene.update({"id": name, "mood": "night"})
    _, errors, _ = plan_mod.validate_scene(scene, 1, set())
    assert errors == []
    assert repaired == [], f"sample cues should all be spoken: {repaired}"
    board = {"narration": narration}
    assert stages.check_scene(scene, board, 1, set(), False) == []


def test_recipes_survive_sparse_slots():
    # A small model may fill only the required fields; every recipe must still build.
    for name, r in recipes.RECIPES.items():
        narration, full = r.sample
        minimal = {k: full[k] for k in r.schema.get("required", []) if k in full}
        scene, _ = recipes.build_scene(name, minimal, narration)
        scene.update({"id": name, "mood": "day"})
        _, errors, _ = plan_mod.validate_scene(scene, 1, set())
        assert errors == [], (name, errors)


def test_unspoken_cue_is_repaired_not_fatal():
    c = recipes.Cues("The browser sends a request and waits for the server to answer.")
    assert c.get("sends a request", 0.1) == "sends a request"
    assert c.get("fires off a request", 0.1) == "request"  # nearest spoken content word
    fallback = c.get("totally unrelated words", 0.9)
    assert fallback and " ".join(fallback.split()) in c.text
    assert len(c.repaired) == 2


class FakeLLM:
    """Replays canned structured replies: first the recipe choice, then the slots."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.schemas = []

    def json(self, system, user, schema=None, **kw):
        self.schemas.append(schema)
        return self.replies.pop(0)


def test_direct_scene_wires_choice_and_slots():
    narration, slots = recipes.RECIPES["exchange"].sample
    sb = {"scenes": [{"id": "intro", "narration": "Hello there.", "mood": "night"},
                     {"id": "Talk!", "narration": narration, "mood": "dusk", "transition": {"type": "iris", "actor": "nope"}, "purpose": "mechanism"}]}
    prev = {"id": "intro", "actors": [{"id": "floor", "type": "shape"}, {"id": "hero", "type": "prop", "at": [6, 7]}]}
    llm = FakeLLM([{"recipe": "exchange", "why": "two parties talk"}, slots])
    scene = stages.direct_scene(llm, {"title": "T", "analogy": {}}, sb, 1, prev, ["hook"])
    assert scene["recipe"] == "exchange" and scene["id"] == "talk_" and scene["mood"] == "dusk"
    assert scene["transition"] == {"type": "iris", "actor": "hero"}  # retargeted to a real previous actor
    assert llm.schemas[0]["properties"]["recipe"]["enum"] and llm.schemas[1] == recipes.RECIPES["exchange"].schema


def test_no_recipe_three_times_running():
    narration, slots = recipes.RECIPES["flow"].sample
    sb = {"scenes": [{"narration": "a"}, {"narration": "b"}, {"narration": narration, "mood": "night"}]}
    llm = FakeLLM([{"recipe": "flow"}, slots])
    stages.direct_scene(llm, {"title": "T"}, sb, 2, None, ["exchange", "exchange"])
    assert "exchange" not in llm.schemas[0]["properties"]["recipe"]["enum"]
