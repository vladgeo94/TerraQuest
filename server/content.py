"""Loads world/stage/question content from TOML files in content/worlds."""

import random
import tomllib
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content" / "worlds"

QUESTION_TYPES = {"single", "multi", "fill", "order"}


class ContentError(Exception):
    pass


def _validate_question(q, where):
    t = q.get("type")
    if t not in QUESTION_TYPES:
        raise ContentError(f"{where}: unknown question type {t!r}")
    if "q" not in q:
        raise ContentError(f"{where}: missing 'q'")
    if t == "single":
        if not isinstance(q.get("answer"), int) or not (0 <= q["answer"] < len(q.get("options", []))):
            raise ContentError(f"{where}: 'answer' must index into 'options'")
    elif t == "multi":
        ans = q.get("answer")
        if not isinstance(ans, list) or not ans or any(not (0 <= a < len(q.get("options", []))) for a in ans):
            raise ContentError(f"{where}: 'answer' must be a list of option indexes")
    elif t == "fill":
        if not isinstance(q.get("answer"), list) or not q["answer"]:
            raise ContentError(f"{where}: 'answer' must be a non-empty list of accepted strings")
    elif t == "order":
        if not isinstance(q.get("items"), list) or len(q["items"]) < 2:
            raise ContentError(f"{where}: 'items' must list at least two steps in the correct order")


def load_worlds():
    worlds = []
    for path in sorted(CONTENT_DIR.glob("*.toml")):
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            raise ContentError(f"{path.name}: {e}") from e
        wid = data.get("id")
        if not wid:
            raise ContentError(f"{path.name}: missing world 'id'")
        data.setdefault("stages", [])
        for si, stage in enumerate(data["stages"]):
            sid = stage.get("id") or f"s{si + 1}"
            stage["id"] = sid
            stage.setdefault("kind", "lab" if "lab" in stage else "quiz")
            stage.setdefault("boss", False)
            stage.setdefault("questions", [])
            for qi, q in enumerate(stage["questions"]):
                q["id"] = q.get("id") or f"{wid}.{sid}.{qi + 1}"
                q.setdefault("obj", data.get("objective_code", ""))
                _validate_question(q, f"{path.name} {sid} question {qi + 1}")
            if stage["kind"] == "lab" and "lab" not in stage:
                raise ContentError(f"{path.name} {sid}: lab stage needs a [stages.lab] table")
        worlds.append(data)
    worlds.sort(key=lambda w: w.get("order", 0))
    return worlds


class Content:
    def __init__(self):
        self.reload()

    def reload(self):
        self.worlds = load_worlds()
        self.questions = {}
        self.stages = {}
        for w in self.worlds:
            for s in w["stages"]:
                self.stages[(w["id"], s["id"])] = (w, s)
                for q in s["questions"]:
                    self.questions[q["id"]] = (w, s, q)

    def world(self, wid):
        return next((w for w in self.worlds if w["id"] == wid), None)

    def stage(self, wid, sid):
        return self.stages.get((wid, sid), (None, None))[1]

    def all_quiz_questions(self):
        return [q for (_w, _s, q) in self.questions.values()]


def public_question(q, rng=None):
    """Strip the answer so the browser cannot peek."""
    out = {"id": q["id"], "type": q["type"], "q": q["q"], "obj": q.get("obj", "")}
    if q.get("code"):
        out["code"] = q["code"]
    if q.get("hint"):
        out["has_hint"] = True
    if q["type"] in ("single", "multi"):
        # Shuffle so the right answer isn't always in the same slot; keys keep the original indexes for grading.
        keys = list(range(len(q["options"])))
        if q.get("shuffle_options", True) and not any("above" in o.lower() for o in q["options"]):
            (rng or random.Random()).shuffle(keys)
        out["options"] = [q["options"][i] for i in keys]
        out["option_keys"] = keys
        if q["type"] == "multi":
            out["pick"] = len(q["answer"])
    elif q["type"] == "order":
        items = list(enumerate(q["items"]))
        rng = rng or random.Random()
        while True:
            rng.shuffle(items)
            if [i for i, _ in items] != list(range(len(items))) or len(items) < 2:
                break
        out["items"] = [{"key": i, "text": t} for i, t in items]
    elif q["type"] == "fill":
        out["placeholder"] = q.get("placeholder", "")
    return out


def _norm(s, case_sensitive):
    s = " ".join(str(s).strip().split())
    return s if case_sensitive else s.lower()


def grade(q, answer):
    t = q["type"]
    if t == "single":
        ok = answer == q["answer"]
        correct = q["answer"]
    elif t == "multi":
        ok = isinstance(answer, list) and sorted(set(answer)) == sorted(q["answer"])
        correct = q["answer"]
    elif t == "fill":
        cs = q.get("case_sensitive", False)
        ok = _norm(answer or "", cs) in {_norm(a, cs) for a in q["answer"]}
        correct = q["answer"][0]
    else:  # order: answer is the list of original indexes in the order the player chose
        ok = answer == list(range(len(q["items"])))
        correct = q["items"]
    return {"correct": ok, "answer": correct, "explain": q.get("explain", ""), "docs": q.get("docs", "")}
