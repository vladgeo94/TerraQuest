"""Player progress: XP, stars, streaks, the respawn (review) queue and exam history."""

import datetime as dt
import json
import math
import threading

from paths import DATA_DIR

PROGRESS_FILE = DATA_DIR / "progress.json"

LEVEL_TITLES = [
    "Init Novice", "HCL Scribbler", "Plan Reader", "Apply Apprentice", "State Keeper",
    "Module Smith", "Backend Wrangler", "Drift Hunter", "Workspace Warden", "Terraform Associate",
]

XP_CORRECT = 10
XP_CORRECT_BOSS = 20
XP_LAB = 50
XP_PER_STAR = 10
XP_EXAM_PASS = 100  # once, the first time a practice exam is passed
REVIEW_CLEAR_STREAK = 2
VERSION = 3  # v2: question XP paid once per question; v3: star/lab XP paid once, practice runs not saved

_lock = threading.Lock()


def _default():
    return {
        "version": VERSION,
        "xp": 0,
        "xp_awarded": [],
        "stages": {},
        "streak": {"last": None, "count": 0, "best": 0},
        "missed": {},
        "exams": [],
        "settings": {"unlock_all": False},
        "answered": 0,
        "correct": 0,
    }


def load():
    with _lock:
        if PROGRESS_FILE.exists():
            try:
                data = json.loads(PROGRESS_FILE.read_text())
                base = _default()
                base["version"] = 1  # files written before versioning
                base.update(data)
                return base
            except (json.JSONDecodeError, OSError):
                pass
        return _default()


def save(p):
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = PROGRESS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(p, indent=2))
        tmp.replace(PROGRESS_FILE)


def reset():
    p = _default()
    save(p)
    return p


def level_info(xp):
    level = int(math.sqrt(xp / 60)) + 1
    cur = 60 * (level - 1) ** 2
    nxt = 60 * level ** 2
    title = LEVEL_TITLES[min(level - 1, len(LEVEL_TITLES) - 1)]
    return {"level": level, "title": title, "xp": xp, "level_xp": cur, "next_xp": nxt}


def touch_streak(p):
    today = dt.date.today()
    last = p["streak"].get("last")
    last = dt.date.fromisoformat(last) if last else None
    if last == today:
        return
    if last == today - dt.timedelta(days=1):
        p["streak"]["count"] += 1
    else:
        p["streak"]["count"] = 1
    p["streak"]["best"] = max(p["streak"]["best"], p["streak"]["count"])
    p["streak"]["last"] = today.isoformat()


def question_xp(boss):
    return XP_CORRECT_BOSS if boss else XP_CORRECT


def record_answer(p, qid, correct, boss=False):
    """Track the answer; XP is paid only the first time a question is answered correctly."""
    touch_streak(p)
    p["answered"] += 1
    gained = 0
    if correct:
        p["correct"] += 1
        if qid not in p["xp_awarded"]:
            p["xp_awarded"].append(qid)
            gained = question_xp(boss)
    m = p["missed"]
    if correct:
        if qid in m:
            m[qid]["streak"] += 1
            if m[qid]["streak"] >= REVIEW_CLEAR_STREAK:
                del m[qid]
    else:
        entry = m.setdefault(qid, {"misses": 0, "streak": 0})
        entry["misses"] += 1
        entry["streak"] = 0
    p["xp"] += gained
    return gained


def record_stage(p, key, stars, score, lab=False):
    """Store best result for a stage; return XP for stars (and lab completion) never paid before.

    `stars` is what the stage shows now (a lab reset clears it); `stars_paid` remembers the most
    stars ever paid for, so earning stars back after a reset doesn't pay XP twice.
    """
    prev = p["stages"].get(key, {"stars": 0, "best": 0, "completed": False, "plays": 0})
    paid = prev.get("stars_paid", 0)
    prev["stars"] = max(prev["stars"], stars)
    prev["best"] = max(prev["best"], score)
    prev["completed"] = prev["completed"] or stars > 0
    prev["plays"] = prev.get("plays", 0) + 1
    prev["stars_paid"] = max(paid, stars)
    bonus = max(0, stars - paid) * XP_PER_STAR
    if lab and stars > 0 and not prev.get("lab_paid"):
        prev["lab_paid"] = True
        bonus += XP_LAB
    p["stages"][key] = prev
    p["xp"] += bonus
    return bonus


def reset_stage(p, key):
    """Clear a stage's stars and best score. It stays completed (later stages stay unlocked) and XP is kept."""
    rec = p["stages"].get(key)
    if rec:
        rec["stars"] = 0
        rec["best"] = 0


def recompute_xp(p, boss_of):
    """Total XP from what has been paid for. boss_of: {qid: is_boss_question}."""
    xp = sum(question_xp(boss_of.get(q, False)) for q in p["xp_awarded"])
    for rec in p["stages"].values():
        xp += rec.get("stars_paid", 0) * XP_PER_STAR + (XP_LAB if rec.get("lab_paid") else 0)
    if p.get("exam_bonus_paid"):
        xp += XP_EXAM_PASS
    return xp


def migrate(p, quiz_stages, lab_stages):
    """Recompute XP for v1 progress files, which paid question XP on every attempt.

    quiz_stages: {stage_key: [(qid, boss), ...]}; lab_stages: set of lab stage keys.
    v1 didn't record which questions were ever answered correctly, so questions in completed
    stages count as earned, except ones still in the respawn queue that were never answered right since.
    """
    if p.get("version", 1) >= 2:
        return False
    awarded, xp = [], 0
    for key, rec in p["stages"].items():
        xp += rec.get("stars", 0) * XP_PER_STAR
        if not rec.get("completed"):
            continue
        if key in lab_stages:
            xp += XP_LAB
        for qid, boss in quiz_stages.get(key, []):
            if p["missed"].get(qid, {}).get("streak", 1) == 0:
                continue
            awarded.append(qid)
            xp += question_xp(boss)
    if any(e.get("passed") for e in p["exams"]):
        xp += XP_EXAM_PASS
    p["xp_awarded"] = awarded
    p["xp"] = xp
    p["version"] = 2
    return True
