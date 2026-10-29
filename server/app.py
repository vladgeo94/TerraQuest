"""TerraQuest local server: serves the web UI, the game API, and a Terraform HTTP state backend."""

import argparse
import json
import mimetypes
import random
import shutil
import subprocess
import sys
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

import labs  # noqa: E402
import progress  # noqa: E402
from content import Content, ContentError, grade, public_question  # noqa: E402
from paths import WEB_DIR  # noqa: E402

OBJECTIVES = {
    "0": "Basics",
    "1": "Infrastructure as Code (IaC) with Terraform",
    "2": "Terraform fundamentals",
    "3": "Core Terraform workflow",
    "4": "Terraform configuration",
    "5": "Terraform modules",
    "6": "Terraform state management",
    "7": "Maintain infrastructure with Terraform",
    "8": "HCP Terraform",
}
# Sub-objective counts per objective in the official 004 content list, used to weight the mock exam.
OBJECTIVE_WEIGHT = {"1": 3, "2": 4, "3": 7, "4": 8, "5": 4, "6": 4, "7": 3, "8": 4}
EXAM_QUESTIONS = 57
EXAM_MINUTES = 60
EXAM_PASS = 0.7

CONTENT = None
EXAMS = {}
_tf_version = None


def tf_version():
    global _tf_version
    if _tf_version is None:
        if shutil.which("terraform") is None:
            _tf_version = ""
        else:
            try:
                out = subprocess.run(["terraform", "version", "-json"], capture_output=True, text=True, timeout=20).stdout
                _tf_version = json.loads(out).get("terraform_version", "")
            except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired):
                _tf_version = "unknown"
    return _tf_version


def stage_key(wid, sid):
    return f"{wid}/{sid}"


def world_cleared(p, w):
    if not w["stages"]:
        return True
    gate = next((s for s in w["stages"] if s["boss"]), w["stages"][-1])
    return p["stages"].get(stage_key(w["id"], gate["id"]), {}).get("completed", False)


def unlock_map(p, honor_practice=True):
    """Return {(wid, sid): unlocked} plus world unlocks. honor_practice=False gives normal progression."""
    unlock_all = honor_practice and p["settings"].get("unlock_all")
    worlds, stages = {}, {}
    prev_cleared = True
    for w in CONTENT.worlds:
        w_open = unlock_all or prev_cleared
        worlds[w["id"]] = w_open
        prev_done = True
        for s in w["stages"]:
            stages[(w["id"], s["id"])] = unlock_all or (w_open and prev_done)
            prev_done = p["stages"].get(stage_key(w["id"], s["id"]), {}).get("completed", False)
        prev_cleared = world_cleared(p, w)
    return worlds, stages, unlock_all or prev_cleared


def is_practice(p, wid, sid):
    """A stage is a practice run when only practice mode makes it playable. Practice runs save nothing."""
    if not p["settings"].get("unlock_all"):
        return False
    return not unlock_map(p, honor_practice=False)[1][(wid, sid)]


def exam_is_practice(p):
    return bool(p["settings"].get("unlock_all")) and not unlock_map(p, honor_practice=False)[2]


def prune_practice(p):
    """Drop records of stages that normal progression hadn't unlocked (earned in practice mode)."""
    removed = []
    prev_cleared = True
    for w in CONTENT.worlds:
        prev_done = True
        for s in w["stages"]:
            key = stage_key(w["id"], s["id"])
            if not (prev_cleared and prev_done) and key in p["stages"]:
                del p["stages"][key]
                removed.append(s)
            prev_done = p["stages"].get(key, {}).get("completed", False)
        prev_cleared = world_cleared(p, w)
    qids = {q["id"] for s in removed for q in s["questions"]}
    p["xp_awarded"] = [q for q in p["xp_awarded"] if q not in qids]
    p["missed"] = {q: v for q, v in p["missed"].items() if q not in qids}
    return removed


def upgrade_progress(p):
    """Bring older progress files up to the current rules. Returns a description, or None if nothing changed."""
    if p.get("version", 1) >= progress.VERSION:
        return None
    old_xp = p["xp"]
    quiz = {stage_key(w["id"], s["id"]): [(q["id"], s["boss"]) for q in s["questions"]] for (w, s) in CONTENT.stages.values()}
    lab_keys = {stage_key(w["id"], s["id"]) for (w, s) in CONTENT.stages.values() if s["kind"] == "lab"}
    progress.migrate(p, quiz, lab_keys)
    for key, rec in p["stages"].items():
        rec.setdefault("stars_paid", rec.get("stars", 0))
        if key in lab_keys and rec.get("completed"):
            rec.setdefault("lab_paid", True)
    removed = prune_practice(p)
    p["exam_bonus_paid"] = any(e.get("passed") and not e.get("practice") for e in p["exams"])
    p["xp"] = progress.recompute_xp(p, {q["id"]: s["boss"] for (_w, s) in CONTENT.stages.values() for q in s["questions"]})
    p["version"] = progress.VERSION
    note = f"XP {old_xp} → {p['xp']}"
    if removed:
        note += f"; removed practice-mode results for: {', '.join(s['title'] for s in removed)}"
    return note


def overview():
    p = progress.load()
    w_open, s_open, exam_open = unlock_map(p)
    _, s_normal, exam_normal = unlock_map(p, honor_practice=False)
    worlds = []
    total_stars = earned = 0
    for w in CONTENT.worlds:
        stages = []
        for s in w["stages"]:
            rec = p["stages"].get(stage_key(w["id"], s["id"]), {})
            total_stars += 3
            earned += rec.get("stars", 0)
            stages.append({
                "id": s["id"], "title": s["title"], "kind": s["kind"], "boss": s["boss"],
                "questions": len(s["questions"]), "stars": rec.get("stars", 0),
                "completed": rec.get("completed", False), "best": rec.get("best", 0),
                "unlocked": s_open[(w["id"], s["id"])],
                "practice": s_open[(w["id"], s["id"])] and not s_normal[(w["id"], s["id"])],
            })
        worlds.append({
            "id": w["id"], "title": w["title"], "subtitle": w.get("subtitle", ""), "icon": w.get("icon", "🌍"),
            "objective": w.get("objective", ""), "unlocked": w_open[w["id"]], "cleared": world_cleared(p, w),
            "stages": stages, "intro": w.get("intro", ""),
        })
    best_exam = max((e["score"] for e in p["exams"]), default=None)
    return {
        "player": progress.level_info(p["xp"]),
        "streak": p["streak"],
        "stars": {"earned": earned, "total": total_stars},
        "accuracy": round(100 * p["correct"] / p["answered"]) if p["answered"] else None,
        "answered": p["answered"],
        "review_count": len([q for q in p["missed"] if q in CONTENT.questions]),
        "exam": {"unlocked": exam_open, "practice": exam_open and not exam_normal, "best": best_exam, "history": p["exams"][-10:], "questions": EXAM_QUESTIONS, "minutes": EXAM_MINUTES},
        "settings": p["settings"],
        "terraform": tf_version(),
        "worlds": worlds,
    }


def stage_payload(wid, sid):
    w, s = CONTENT.stages.get((wid, sid), (None, None))
    if not s:
        return None
    p = progress.load()
    _, s_open, _ = unlock_map(p)
    out = {
        "world": {"id": w["id"], "title": w["title"], "icon": w.get("icon", "")},
        "id": s["id"], "title": s["title"], "kind": s["kind"], "boss": s["boss"],
        "lesson": s.get("lesson", ""), "unlocked": s_open[(wid, sid)],
        "practice": is_practice(p, wid, sid),
        "pass": s.get("pass", 0.8 if s["boss"] else 0.7),
        "record": p["stages"].get(stage_key(wid, sid), {}),
    }
    if s["kind"] == "quiz":
        qs = list(s["questions"])
        if s.get("shuffle", s["boss"]):
            random.shuffle(qs)
        out["questions"] = [public_question(q) for q in qs]
    else:
        lab = s["lab"]
        out["lab"] = {
            "goal": lab.get("goal", ""),
            "hints": len(lab.get("hints", [])),
            "actions": [{"id": a["id"], "label": a["label"]} for a in lab.get("actions", [])],
            "checks": [c.get("msg", c["type"]) for c in lab.get("checks", [])],
            "suggested": lab.get("suggested", ["terraform init", "terraform validate", "terraform plan", "terraform apply"]),
            "backend_panel": lab.get("backend_panel", False),
            "solution": bool(lab.get("solution")),
        }
    return out


def quiz_stars(correct, total, hints, pass_ratio):
    ratio = correct / total if total else 0
    if ratio < pass_ratio:
        return 0
    if ratio == 1 and hints == 0:
        return 3
    if ratio >= 0.85:
        return 2
    return 1


def lab_stars(attempts, hints):
    if attempts <= 1 and hints == 0:
        return 3
    if attempts <= 3 and hints <= 1:
        return 2
    return 1


def start_exam():
    pool = {}
    for q in CONTENT.all_quiz_questions():
        o = str(q.get("obj", ""))[:1]
        if o in OBJECTIVE_WEIGHT:
            pool.setdefault(o, []).append(q)
    total_w = sum(OBJECTIVE_WEIGHT.values())
    picked = []
    for o, wgt in OBJECTIVE_WEIGHT.items():
        n = round(EXAM_QUESTIONS * wgt / total_w)
        cand = pool.get(o, [])
        picked += random.sample(cand, min(n, len(cand)))
    rest = [q for qs in pool.values() for q in qs if q not in picked]
    random.shuffle(rest)
    while len(picked) < EXAM_QUESTIONS and rest:
        picked.append(rest.pop())
    picked = picked[:EXAM_QUESTIONS]
    random.shuffle(picked)
    eid = uuid.uuid4().hex
    practice = exam_is_practice(progress.load())
    EXAMS[eid] = {"ids": [q["id"] for q in picked], "started": time.time(), "practice": practice}
    return {"id": eid, "minutes": EXAM_MINUTES, "practice": practice, "questions": [public_question(q) for q in picked]}


def submit_exam(eid, answers):
    ex = EXAMS.pop(eid, None)
    if not ex:
        return None
    p = progress.load()
    by_obj = {}
    details = []
    correct = gained = 0
    for qid in ex["ids"]:
        _w, _s, q = CONTENT.questions[qid]
        r = grade(q, answers.get(qid))
        o = str(q.get("obj", "0"))[:1]
        b = by_obj.setdefault(o, {"name": OBJECTIVES.get(o, o), "correct": 0, "total": 0})
        b["total"] += 1
        if r["correct"]:
            correct += 1
            b["correct"] += 1
        if not ex["practice"]:
            gained += progress.record_answer(p, qid, r["correct"], boss=_s["boss"])
        details.append({"question": public_question(q), "given": answers.get(qid), **r, "full": q})
    score = round(100 * correct / len(ex["ids"])) if ex["ids"] else 0
    elapsed = int(time.time() - ex["started"])
    passed = score >= EXAM_PASS * 100
    if passed and not ex["practice"] and not p.get("exam_bonus_paid"):
        p["exam_bonus_paid"] = True
        gained += progress.XP_EXAM_PASS
        p["xp"] += progress.XP_EXAM_PASS
    p["exams"].append({"score": score, "correct": correct, "total": len(ex["ids"]), "seconds": elapsed,
                       "date": time.strftime("%Y-%m-%d %H:%M"), "passed": passed, "practice": ex["practice"]})
    progress.save(p)
    for d in details:
        q = d.pop("full")
        if q["type"] in ("single", "multi"):
            d["options"] = q["options"]
        if q["type"] == "order":
            d["items"] = q["items"]
    return {"score": score, "correct": correct, "total": len(ex["ids"]), "passed": score >= EXAM_PASS * 100,
            "seconds": elapsed, "objectives": dict(sorted(by_obj.items())), "details": details, "xp": gained,
            "practice": ex["practice"]}


class Handler(BaseHTTPRequestHandler):
    server_version = "TerraQuest/1.0"

    def log_message(self, fmt, *args):
        if self.server.verbose:
            super().log_message(fmt, *args)

    # ------------------------------------------------------------ helpers
    def _send(self, code, body=b"", ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data, code=200):
        self._send(code, json.dumps(data).encode())

    def _err(self, msg, code=400):
        self._json({"error": msg}, code)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _jbody(self):
        raw = self._body()
        return json.loads(raw) if raw else {}

    # ------------------------------------------------------------ routing
    def do_GET(self):
        url = urlparse(self.path)
        if url.path.startswith("/tfstate/"):
            return self._backend("GET", url.path[len("/tfstate/"):])
        if url.path.startswith("/api/"):
            return self._api_get(url.path, parse_qs(url.query))
        return self._static(url.path)

    do_HEAD = do_GET

    def do_POST(self):
        url = urlparse(self.path)
        if url.path.startswith("/tfstate/"):
            return self._backend("POST", url.path[len("/tfstate/"):])
        try:
            return self._api_post(url.path, self._jbody())
        except labs.LabError as e:
            return self._err(str(e))
        except json.JSONDecodeError:
            return self._err("Bad JSON")

    def do_DELETE(self):
        url = urlparse(self.path)
        if url.path.startswith("/tfstate/"):
            return self._backend("DELETE", url.path[len("/tfstate/"):])
        self._err("Not found", 404)

    def do_LOCK(self):
        self._backend("LOCK", urlparse(self.path).path[len("/tfstate/"):])

    def do_UNLOCK(self):
        self._backend("UNLOCK", urlparse(self.path).path[len("/tfstate/"):])

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        target = (WEB_DIR / path.lstrip("/")).resolve()
        if WEB_DIR.resolve() not in target.parents or not target.is_file():
            target = WEB_DIR / "index.html"
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    def _api_get(self, path, qs):
        g = lambda k: (qs.get(k) or [""])[0]  # noqa: E731
        if path == "/api/overview":
            return self._json(overview())
        if path == "/api/stage":
            data = stage_payload(g("w"), g("s"))
            return self._json(data) if data else self._err("Unknown stage", 404)
        if path == "/api/review":
            p = progress.load()
            ids = [q for q in p["missed"] if q in CONTENT.questions]
            random.shuffle(ids)
            return self._json({"questions": [public_question(CONTENT.questions[q][2]) for q in ids[:10]], "total": len(ids)})
        if path == "/api/backend":
            return self._json(labs.backend_overview())
        if path == "/api/exam/start":
            return self._json(start_exam())
        return self._err("Not found", 404)

    def _api_post(self, path, b):
        if path == "/api/answer":
            entry = CONTENT.questions.get(b.get("qid"))
            if not entry:
                return self._err("Unknown question", 404)
            w, s, q = entry
            r = grade(q, b.get("answer"))
            p = progress.load()
            if not b.get("review") and is_practice(p, w["id"], s["id"]):
                r.update({"xp": 0, "practice": True})
                return self._json(r)
            r["xp"] = progress.record_answer(p, q["id"], r["correct"], boss=s["boss"])
            r["xp_already"] = r["correct"] and not r["xp"]
            progress.save(p)
            return self._json(r)
        if path == "/api/hint":
            entry = CONTENT.questions.get(b.get("qid"))
            return self._json({"hint": entry[2].get("hint", "No hint for this one.")}) if entry else self._err("Unknown question", 404)
        if path == "/api/stage/finish":
            s = CONTENT.stage(b.get("w"), b.get("s"))
            if not s or s["kind"] != "quiz":
                return self._err("Unknown quiz stage", 404)
            total = len(s["questions"])
            correct = min(int(b.get("correct", 0)), total)
            stars = quiz_stars(correct, total, int(b.get("hints", 0)), s.get("pass", 0.8 if s["boss"] else 0.7))
            p = progress.load()
            score = round(100 * correct / total) if total else 0
            if is_practice(p, b["w"], b["s"]):
                return self._json({"stars": stars, "score": score, "bonus": 0, "passed": stars > 0, "practice": True})
            bonus = progress.record_stage(p, stage_key(b["w"], b["s"]), stars, score)
            progress.save(p)
            return self._json({"stars": stars, "score": score, "bonus": bonus, "passed": stars > 0})
        if path == "/api/settings":
            p = progress.load()
            p["settings"].update({k: v for k, v in b.items() if k in ("unlock_all",)})
            progress.save(p)
            return self._json(p["settings"])
        if path == "/api/reset":
            progress.reset()
            if b.get("labs"):
                shutil.rmtree(labs.LABS_DIR, ignore_errors=True)
                shutil.rmtree(labs.BACKEND_DIR, ignore_errors=True)
            return self._json({"ok": True})
        if path == "/api/reload":
            try:
                CONTENT.reload()
            except ContentError as e:
                return self._err(str(e))
            return self._json({"ok": True, "questions": len(CONTENT.questions)})
        if path == "/api/exam/submit":
            res = submit_exam(b.get("id"), b.get("answers", {}))
            return self._json(res) if res else self._err("Exam session not found (did the server restart?)", 404)
        if path.startswith("/api/lab/"):
            return self._lab(path[len("/api/lab/"):], b)
        return self._err("Not found", 404)

    def _lab(self, action, b):
        wid, sid = b.get("w"), b.get("s")
        s = CONTENT.stage(wid, sid)
        if not s or s["kind"] != "lab":
            return self._err("Unknown lab", 404)
        lab = s["lab"]
        if action in ("open", "reset"):
            labs.setup(wid, sid, lab, reset=action == "reset")
            if action == "reset":
                p = progress.load()
                if not is_practice(p, wid, sid):
                    progress.reset_stage(p, stage_key(wid, sid))
                    progress.save(p)
            meta = labs.load_meta(wid, sid)
            return self._json({"files": labs.list_files(wid, sid), "dir": str(labs.lab_dir(wid, sid)),
                               "setup_output": meta.get("setup_output", ""), "passed": meta.get("passed", False),
                               "hints_used": meta.get("hints", 0)})
        if action == "files":
            return self._json({"files": labs.list_files(wid, sid)})
        if action == "save":
            path = labs.safe_path(labs.lab_dir(wid, sid), b["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(b.get("content", ""), encoding="utf-8")
            return self._json({"ok": True})
        if action == "delete_file":
            path = labs.safe_path(labs.lab_dir(wid, sid), b["path"])
            if path.exists() and path.is_file():
                path.unlink()
            return self._json({"ok": True})
        if action == "run":
            r = labs.run(wid, sid, b.get("cmd", ""))
            r["files"] = labs.list_files(wid, sid)
            return self._json(r)
        if action == "action":
            msg = labs.do_action(wid, sid, lab, b.get("action"))
            return self._json({"message": msg, "files": labs.list_files(wid, sid)})
        if action == "hint":
            i = int(b.get("i", 0))
            hints = lab.get("hints", [])
            if not 0 <= i < len(hints):
                return self._err("No such hint")
            meta = labs.load_meta(wid, sid)
            meta["hints"] = max(meta.get("hints", 0), i + 1)
            labs.save_meta(wid, sid, meta)
            return self._json({"hint": hints[i]})
        if action == "solution":
            meta = labs.load_meta(wid, sid)
            meta["hints"] = max(meta.get("hints", 0), 99)
            labs.save_meta(wid, sid, meta)
            return self._json({"solution": lab.get("solution", "")})
        if action == "check":
            r = labs.run_checks(wid, sid, lab)
            if r["passed"]:
                stars = lab_stars(r["attempts"], r["hints"])
                p = progress.load()
                if is_practice(p, wid, sid):
                    r.update({"stars": stars, "bonus": 0, "practice": True})
                    return self._json(r)
                progress.touch_streak(p)
                bonus = progress.record_stage(p, stage_key(wid, sid), stars, 100, lab=True)
                progress.save(p)
                r.update({"stars": stars, "bonus": bonus})
            return self._json(r)
        return self._err("Unknown lab action", 404)

    # ------------------------------------------------------------ terraform http backend
    def _backend(self, method, name):
        try:
            if method == "GET":
                data = labs.backend_get(name)
                return self._send(200, data) if data is not None else self._send(404, b"")
            if method == "POST":
                lock_id = parse_qs(urlparse(self.path).query).get("ID", [None])[0]
                lock = labs.BACKEND_DIR / f"{name}.lock"
                if lock_id and lock.exists() and json.loads(lock.read_text()).get("ID") != lock_id:
                    return self._send(409, lock.read_bytes())
                labs.backend_put(name, self._body())
                return self._send(200, b"")
            if method == "DELETE":
                labs.backend_delete(name)
                return self._send(200, b"")
            if method == "LOCK":
                info = json.loads(self._body() or b"{}")
                ok, cur = labs.backend_lock(name, info)
                return self._send(200 if ok else HTTPStatus.LOCKED, json.dumps(cur).encode())
            if method == "UNLOCK":
                raw = self._body()
                info = json.loads(raw) if raw else {}
                ok = labs.backend_unlock(name, info.get("ID") or None)
                return self._send(200 if ok else 409, b"")
        except labs.LabError as e:
            return self._send(400, str(e).encode(), "text/plain")


def main():
    global CONTENT
    ap = argparse.ArgumentParser(description="TerraQuest — learn Terraform Associate (004) as a game")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--check-content", action="store_true", help="validate content files and exit")
    args = ap.parse_args()
    try:
        CONTENT = Content()
    except ContentError as e:
        print(f"Content error: {e}", file=sys.stderr)
        sys.exit(2)
    nq = len(CONTENT.questions)
    nl = sum(1 for (_w, s) in CONTENT.stages.values() if s["kind"] == "lab")
    if args.check_content:
        print(f"OK: {len(CONTENT.worlds)} worlds, {len(CONTENT.stages)} stages, {nq} questions, {nl} labs")
        return
    p = progress.load()
    note = upgrade_progress(p)
    if note:
        progress.save(p)
        print(f"Progress upgraded to the new XP rules: {note}.", flush=True)
    labs.BASE_URL = f"http://127.0.0.1:{args.port}"
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.verbose = args.verbose
    srv.daemon_threads = True
    threading.Thread(target=tf_version, daemon=True).start()
    print(f"TerraQuest is running at http://{args.host}:{args.port}  ({nq} questions, {nl} labs)", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBye! Progress is saved.")


if __name__ == "__main__":
    main()
