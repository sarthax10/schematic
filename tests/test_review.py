"""The human review checkpoint: approval is tied to the exact script text, edits are saved
with the same spoken-text cleanup the writer gets, and a revision keeps the current script."""
import json
import shutil
from pathlib import Path

import pytest

from pipeline import library, review, stages

EX = Path(__file__).resolve().parent.parent / "examples" / "token_bucket"


@pytest.fixture
def out(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "DB_PATH", tmp_path / "lib.sqlite")
    d = tmp_path / "rate-limiting"
    d.mkdir()
    shutil.copy(EX / "script.json", d / "script.json")
    shutil.copy(EX / "topic.json", d / "topic.json")
    library.add("Rate limiting", status="awaiting_review", out_dir=str(d))
    return d


def script(out):
    return json.loads((out / "script.json").read_text(encoding="utf-8"))


def test_gate_is_pending_until_approved_and_resets_on_edit(out):
    assert review.gate(out, script(out)) == "pending"
    review.approve(out)
    assert review.gate(out, script(out)) == "approved"
    edited = script(out)
    edited["sections"][0]["text"] += " One more sentence."
    assert review.gate(out, edited) == "pending"  # the approval was for different words


def test_save_applies_spoken_cleanup_and_keeps_other_sections(out):
    before = script(out)
    p = review.save(out, "New title", [{"part": "example", "text": "GitHub (the code host) allows five thousand requests an hour."}])
    after = script(out)
    ex = next(s["text"] for s in after["sections"] if s["part"] == "example")
    assert "(" not in ex and "the code host" in ex
    assert after["title"] == "New title"
    assert [s["text"] for s in after["sections"] if s["part"] != "example"] == [s["text"] for s in before["sections"] if s["part"] != "example"]
    assert p["words"] == len(stages.script_text(after).split())


def test_request_changes_records_notes(out):
    p = review.request_changes(out, ["Use a phone call analogy", "  "])
    assert p["gate"] == "changes_requested"
    assert review.state(out)["notes"] == ["Use a phone call analogy"]


def test_both_review_file_shapes_normalize():
    old = {"first_pass": {"issues": [{"severity": "high"}]}, "second_pass": {"issues": [{"severity": "medium", "quote": "x"}, {"severity": "low"}]}}
    n = review.normalize_review(old)
    assert len(n["passes"]) == 2 and n["unresolved"] == [{"severity": "medium", "quote": "x"}]
    assert review.normalize_review(None) == {"passes": [], "unresolved": []}


def test_packet_reports_length_and_problems(out):
    p = review.packet(out)
    assert p["gate"] == "pending" and p["words"] > 150 and 50 < p["seconds"] < 100
    assert isinstance(p["problems"], list)


class FakeLLM:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    def json(self, system, user, **kw):
        self.prompts.append(user)
        return self.reply


def test_revision_prompt_carries_the_current_script_and_notes():
    current = json.loads((EX / "script.json").read_text(encoding="utf-8"))
    llm = FakeLLM(current)
    stages.write_script(llm, {"topic": "rate limiting"}, feedback=["Use a phone call analogy"], current=current)
    prompt = llm.prompts[0]
    assert "The current script" in prompt and current["sections"][0]["text"] in prompt
    assert "Use a phone call analogy" in prompt and "keep every other sentence" in prompt
