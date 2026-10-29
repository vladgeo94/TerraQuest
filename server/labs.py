"""Hands-on labs: sandbox folders, a guarded terraform runner, and work checkers."""

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from paths import BACKEND_DIR, LABS_DIR, PLUGIN_CACHE

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
ALLOWED_SUBCOMMANDS = {
    "init", "validate", "fmt", "plan", "apply", "destroy", "show", "output", "state",
    "import", "providers", "version", "workspace", "console", "force-unlock", "graph",
    "get", "refresh", "test", "untaint", "taint", "login", "logout",
}
ALLOWED_ENV = re.compile(r"^(TF_LOG|TF_LOG_PATH|TF_LOG_CORE|TF_LOG_PROVIDER|TF_WORKSPACE|TF_VAR_\w+)$")
TIMEOUT = 300
BASE_URL = "http://127.0.0.1:8080"  # set by app.main() so lab files can point at the game's HTTP backend


class LabError(Exception):
    pass


def lab_key(wid, sid):
    return f"{wid}_{sid}"


def lab_dir(wid, sid):
    return LABS_DIR / lab_key(wid, sid)


def _meta_path(wid, sid):
    return LABS_DIR / f"{lab_key(wid, sid)}.meta.json"


def load_meta(wid, sid):
    p = _meta_path(wid, sid)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {"checks": 0, "hints": 0, "history": [], "snapshot": None, "passed": False}


def save_meta(wid, sid, meta):
    LABS_DIR.mkdir(parents=True, exist_ok=True)
    _meta_path(wid, sid).write_text(json.dumps(meta, indent=2))


def safe_path(base, rel):
    p = (base / rel).resolve()
    if base.resolve() not in p.parents and p != base.resolve():
        raise LabError(f"Path {rel!r} is outside the lab folder")
    return p


def list_files(wid, sid):
    d = lab_dir(wid, sid)
    out = []
    if not d.exists():
        return out
    for p in sorted(d.rglob("*")):
        rel = p.relative_to(d)
        if p.is_dir() or any(part.startswith(".terraform") or part == "terraform.tfstate.d" for part in rel.parts):
            continue
        if p.suffix in (".tf", ".tfvars", ".txt", ".json", ".hcl", ".md", ".log", ".tftpl", ".tfstate", ".backup", ".example", ".env", ".conf") or p.name.endswith(".tfvars"):
            if p.stat().st_size > 400_000:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            out.append({"path": str(rel), "content": text,
                        "readonly": p.suffix in (".tfstate", ".backup", ".log") or p.name == ".terraform.lock.hcl"})
    return out


def _env():
    env = os.environ.copy()
    PLUGIN_CACHE.mkdir(parents=True, exist_ok=True)
    env["TF_PLUGIN_CACHE_DIR"] = str(PLUGIN_CACHE)
    env["TF_INPUT"] = "0"
    env["TF_IN_AUTOMATION"] = "1"
    env["CHECKPOINT_DISABLE"] = "1"
    for k in list(env):
        if k.startswith("TF_LOG") or k.startswith("TF_VAR_") or k == "TF_WORKSPACE":
            env.pop(k)
    return env


def parse_command(line):
    """Turn a player command line into (argv, extra_env, stdin)."""
    line = line.strip()
    stdin = None
    m = re.match(r"^echo\s+(.+?)\s*\|\s*(terraform\s+console.*)$", line)
    if m:
        try:
            stdin = " ".join(shlex.split(m.group(1))) + "\n"
        except ValueError as e:
            raise LabError(f"Could not parse command: {e}")
        line = m.group(2)
    try:
        tokens = shlex.split(line)
    except ValueError as e:
        raise LabError(f"Could not parse command: {e}")
    env = {}
    while tokens and "=" in tokens[0] and not tokens[0].startswith("-"):
        k, v = tokens.pop(0).split("=", 1)
        if not ALLOWED_ENV.match(k):
            raise LabError(f"Environment variable {k} is not allowed here (try TF_LOG, TF_LOG_PATH, TF_VAR_name)")
        env[k] = v
    if tokens and tokens[0] == "terraform":
        tokens.pop(0)
    if not tokens:
        raise LabError("Type a terraform command, for example: terraform init")
    if tokens[0] not in ALLOWED_SUBCOMMANDS:
        raise LabError(f"'{tokens[0]}' is not a terraform subcommand allowed in labs. Allowed: {', '.join(sorted(ALLOWED_SUBCOMMANDS))}")
    sub = tokens[0]
    if sub == "console" and stdin is None:
        raise LabError("The console is interactive. In labs, pipe an expression into it: echo 'upper(\"hi\")' | terraform console")
    if sub in ("apply", "destroy") and "-auto-approve" not in tokens:
        tokens.insert(1, "-auto-approve")
    if sub == "init" and "-migrate-state" in tokens and "-force-copy" not in tokens:
        tokens.append("-force-copy")  # labs can't answer the interactive "copy existing state?" prompt
    if sub == "force-unlock" and "-force" not in tokens:
        tokens.insert(1, "-force")
    if sub in ("login", "logout"):
        raise LabError("terraform login opens a browser and stores an HCP token. Run it in your own terminal, not in a lab.")
    return ["terraform", *tokens], env, stdin


def run(wid, sid, line, record=True):
    d = lab_dir(wid, sid)
    if not d.exists():
        raise LabError("Lab is not open yet")
    argv, extra, stdin = parse_command(line)
    env = _env()
    for k, v in extra.items():
        if k == "TF_LOG_PATH":
            v = str(safe_path(d, v))
        env[k] = v
    if shutil.which("terraform") is None:
        raise LabError("terraform is not installed or not on PATH")
    try:
        proc = subprocess.run(argv, cwd=d, env=env, input=stdin, capture_output=True, text=True, timeout=TIMEOUT)
        out = ANSI.sub("", proc.stdout + (("\n" + proc.stderr) if proc.stderr else ""))
        code = proc.returncode
    except subprocess.TimeoutExpired:
        out, code = f"Command timed out after {TIMEOUT}s", 124
    if record:
        meta = load_meta(wid, sid)
        meta["history"] = (meta.get("history", []) + [" ".join(argv)])[-100:]
        save_meta(wid, sid, meta)
    return {"cmd": " ".join(argv), "code": code, "output": out.strip()}


def _tf(d, *args, stdin=None):
    p = subprocess.run(["terraform", *args], cwd=d, env=_env(), capture_output=True, text=True, timeout=TIMEOUT, input=stdin)
    return p.returncode, ANSI.sub("", p.stdout + p.stderr)


def state_json(d):
    if not (d / ".terraform").exists() and not (d / "terraform.tfstate").exists():
        return None
    code, out = _tf(d, "show", "-json")
    if code != 0:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def all_resources(state):
    res = []
    if not state or "values" not in state:
        return res

    def walk(mod):
        res.extend(mod.get("resources", []))
        for c in mod.get("child_modules", []):
            walk(c)

    walk(state["values"].get("root_module", {}))
    return res


def find_resource(state, address):
    return next((r for r in all_resources(state) if r["address"] == address), None)


def _dig(values, attr):
    cur = values
    for part in re.split(r"\.|\[|\]", attr):
        if part == "":
            continue
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def config_text(d):
    texts = []
    for p in sorted(d.rglob("*.tf")):
        if ".terraform" in p.parts:
            continue
        texts.append(p.read_text(encoding="utf-8"))
    return "\n".join(texts)


def _template(content):
    return content.lstrip("\n").replace("{{BASE_URL}}", BASE_URL)


def setup(wid, sid, lab, reset=False):
    d = lab_dir(wid, sid)
    if d.exists() and not reset:
        return
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for rel, content in lab.get("files", {}).items():
        p = safe_path(d, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_template(content), encoding="utf-8")
    meta = {"checks": 0, "hints": 0, "history": [], "snapshot": None, "passed": False, "setup_output": ""}
    for name in lab.get("reset_backend", []):
        backend_delete(name)
        backend_unlock(name, force=True)
    outputs = []
    for line in lab.get("setup", []):
        r = run(wid, sid, line, record=False)
        outputs.append(f"$ {r['cmd']}\n{r['output']}")
        if r["code"] != 0:
            outputs.append("(setup step failed — check your internet connection for the first provider download)")
            break
    for rel, content in lab.get("post_setup_files", {}).items():
        p = safe_path(d, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_template(content), encoding="utf-8")
    if lab.get("setup"):
        meta["snapshot"] = state_json(d)
    meta["setup_output"] = "\n\n".join(outputs)
    save_meta(wid, sid, meta)


def do_action(wid, sid, lab, action_id):
    d = lab_dir(wid, sid)
    action = next((a for a in lab.get("actions", []) if a["id"] == action_id), None)
    if not action:
        raise LabError("Unknown action")
    t = action["type"]
    if t == "delete_file":
        p = safe_path(d, action["path"])
        if p.exists():
            p.unlink()
        return f"Deleted {action['path']} behind Terraform's back."
    if t == "write_file":
        p = safe_path(d, action["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_template(action["content"]), encoding="utf-8")
        return f"Someone edited {action['path']} by hand."
    if t == "backend_lock":
        info = {"ID": action.get("lock_id", "c0ffee00-dead-beef-0000-123456789abc"), "Operation": "OperationTypeApply",
                "Who": "teammate@their-laptop", "Version": "1.12.0", "Created": "2026-01-01T09:00:00Z", "Path": action["name"]}
        _write_lock(action["name"], info)
        return f"A teammate's apply crashed and left state '{action['name']}' locked. Run a command to see who holds the lock."
    raise LabError(f"Unknown action type {t}")


# ---------------------------------------------------------------- checks

def run_checks(wid, sid, lab):
    d = lab_dir(wid, sid)
    meta = load_meta(wid, sid)
    cache = {}

    def st():
        if "state" not in cache:
            cache["state"] = state_json(d)
        return cache["state"]

    results = []
    for c in lab.get("checks", []):
        try:
            ok, detail = _check(c, d, st, meta)
        except Exception as e:  # a broken check should explain itself, not crash the lab
            ok, detail = False, f"Check error: {e}"
        results.append({"msg": c.get("msg", c["type"]), "ok": ok, "detail": detail})
        if not ok and c.get("stop", False):
            break
    passed = all(r["ok"] for r in results) and len(results) == len(lab.get("checks", []))
    meta["checks"] = meta.get("checks", 0) + 1
    meta["passed"] = meta.get("passed") or passed
    save_meta(wid, sid, meta)
    return {"passed": passed, "results": results, "attempts": meta["checks"], "hints": meta.get("hints", 0)}


def _check(c, d, st, meta):
    t = c["type"]
    if t == "file_exists":
        return safe_path(d, c["path"]).exists(), ""
    if t == "file_absent":
        return not safe_path(d, c["path"]).exists(), ""
    if t in ("file_contains", "file_regex"):
        p = safe_path(d, c["path"])
        if not p.exists():
            return False, f"{c['path']} does not exist yet"
        text = p.read_text(encoding="utf-8", errors="replace")
        if t == "file_contains":
            return c["text"] in text, ""
        return re.search(c["pattern"], text, re.M) is not None, ""
    if t == "config_regex":
        return re.search(c["pattern"], config_text(d), re.M | re.S) is not None, ""
    if t == "config_not_regex":
        return re.search(c["pattern"], config_text(d), re.M | re.S) is None, ""
    if t == "validate_ok":
        code, out = _tf(d, "validate")
        return code == 0, "" if code == 0 else out[-600:]
    if t == "fmt_ok":
        code, out = _tf(d, "fmt", "-check", "-recursive")
        return code == 0, "" if code == 0 else "Files not formatted: " + out.strip().replace("\n", ", ")
    if t == "lockfile":
        p = d / ".terraform.lock.hcl"
        if not p.exists():
            return False, "No .terraform.lock.hcl yet — run terraform init"
        return c.get("provider", "") in p.read_text(), ""
    if t == "initialized":
        return (d / ".terraform").exists(), "Run terraform init first" if not (d / ".terraform").exists() else ""
    if t == "resource":
        return find_resource(st(), c["address"]) is not None, ""
    if t == "no_resource":
        return find_resource(st(), c["address"]) is None, ""
    if t == "state_empty":
        return len([r for r in all_resources(st()) if r.get("mode") == "managed"]) == 0, ""
    if t == "resource_count":
        n = len([r for r in all_resources(st()) if r["type"] == c["rtype"] and r.get("mode", "managed") == c.get("mode", "managed")])
        ok = n >= c["count"] if c.get("at_least") else n == c["count"]
        return ok, f"found {n}"
    if t == "attr":
        r = find_resource(st(), c["address"])
        if not r:
            return False, f"{c['address']} is not in state"
        v = _dig(r.get("values", {}), c["attr"])
        if "equals" in c:
            return v == c["equals"], f"is {v!r}"
        if "regex" in c:
            return v is not None and re.search(c["regex"], str(v)) is not None, f"is {v!r}"
        return v is not None, ""
    if t == "output":
        s = st()
        outs = (s or {}).get("values", {}).get("outputs", {})
        o = outs.get(c["name"])
        if o is None:
            return False, f"No output named {c['name']} in state — did you apply?"
        if "sensitive" in c and o.get("sensitive") != c["sensitive"]:
            return False, f"sensitive is {o.get('sensitive')}"
        if "equals" in c:
            return o.get("value") == c["equals"], f"is {o.get('value')!r}"
        if "regex" in c:
            return re.search(c["regex"], json.dumps(o.get("value"))) is not None, f"is {o.get('value')!r}"
        return True, ""
    if t == "no_changes":
        code, out = _tf(d, "plan", "-detailed-exitcode", "-lock=false")
        if code == 0:
            return True, ""
        if code == 2:
            summary = re.search(r"Plan: .*", out)
            return False, "Plan still has changes: " + (summary.group(0) if summary else "see terraform plan")
        return False, out[-600:]
    if t in ("command_ok", "command_fails"):
        argv, extra, stdin = parse_command(c["cmd"])
        env = _env()
        env.update(extra)
        p = subprocess.run(argv, cwd=d, env=env, input=stdin, capture_output=True, text=True, timeout=TIMEOUT)
        out = ANSI.sub("", p.stdout + p.stderr)
        want_ok = t == "command_ok"
        ok = (p.returncode == 0) == want_ok
        if ok and c.get("output_regex"):
            ok = re.search(c["output_regex"], out, re.S | re.I) is not None
        return ok, "" if ok else out[-600:]
    if t == "snapshot_same":
        snap = meta.get("snapshot")
        before = find_resource(snap, c["was"]) if snap else None
        now = find_resource(st(), c["address"])
        if not before:
            return False, "No starting snapshot — reset the lab"
        if not now:
            return False, f"{c['address']} is not in state"
        a, b = _dig(before["values"], c["attr"]), _dig(now["values"], c["attr"])
        if c.get("expect_change"):
            return a != b, "" if a != b else f"{c['attr']} is still {a!r}, so the resource was not replaced yet"
        return a == b, "" if a == b else f"{c['attr']} changed from {a!r} to {b!r} (the resource was replaced)"
    if t == "backend_state":
        p = BACKEND_DIR / f"{c['name']}.tfstate"
        if not p.exists():
            return False, "The game's HTTP backend has no state with that name yet"
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError:
            return False, "State file is not valid JSON"
        return len(data.get("resources", [])) >= c.get("min_resources", 1), ""
    if t == "backend_unlocked":
        return not (BACKEND_DIR / f"{c['name']}.lock").exists(), "State is still locked"
    if t == "no_local_state":
        p = d / "terraform.tfstate"
        if not p.exists():
            return True, ""
        try:
            data = json.loads(p.read_text())
            return not data.get("resources"), "terraform.tfstate still holds resources locally"
        except json.JSONDecodeError:
            return True, ""
    if t == "workspace_exists":
        code, out = _tf(d, "workspace", "list")
        names = [ln.strip(" *") for ln in out.splitlines()]
        return c["name"] in names, ""
    if t == "workspace_resource":
        p = d / "terraform.tfstate.d" / c["workspace"] / "terraform.tfstate"
        if not p.exists():
            return False, f"No state for workspace {c['workspace']} yet"
        data = json.loads(p.read_text())
        return len(data.get("resources", [])) > 0, ""
    if t == "history":
        hist = " \n".join(meta.get("history", []))
        return re.search(c["pattern"], hist) is not None, ""
    raise LabError(f"Unknown check type {t}")


# ---------------------------------------------------------------- HTTP backend

def _name_ok(name):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", name):
        raise LabError("Bad state name")
    return name


def backend_get(name):
    p = BACKEND_DIR / f"{_name_ok(name)}.tfstate"
    return p.read_bytes() if p.exists() else None


def backend_put(name, body):
    BACKEND_DIR.mkdir(parents=True, exist_ok=True)
    (BACKEND_DIR / f"{_name_ok(name)}.tfstate").write_bytes(body)


def backend_delete(name):
    p = BACKEND_DIR / f"{_name_ok(name)}.tfstate"
    if p.exists():
        p.unlink()


def _write_lock(name, info):
    BACKEND_DIR.mkdir(parents=True, exist_ok=True)
    (BACKEND_DIR / f"{_name_ok(name)}.lock").write_text(json.dumps(info))


def backend_lock(name, info):
    p = BACKEND_DIR / f"{_name_ok(name)}.lock"
    if p.exists():
        return False, json.loads(p.read_text())
    _write_lock(name, info)
    return True, info


def backend_unlock(name, lock_id=None, force=False):
    p = BACKEND_DIR / f"{_name_ok(name)}.lock"
    if not p.exists():
        return True
    cur = json.loads(p.read_text())
    if force or lock_id is None or cur.get("ID") == lock_id:
        p.unlink()
        return True
    return False


def backend_overview():
    out = []
    if BACKEND_DIR.exists():
        for p in sorted(BACKEND_DIR.glob("*.tfstate")):
            name = p.stem
            lock = BACKEND_DIR / f"{name}.lock"
            try:
                data = json.loads(p.read_text())
                n = len(data.get("resources", []))
                serial = data.get("serial")
            except json.JSONDecodeError:
                n, serial = 0, None
            out.append({"name": name, "resources": n, "serial": serial,
                        "lock": json.loads(lock.read_text()) if lock.exists() else None})
        for lock in BACKEND_DIR.glob("*.lock"):
            if not (BACKEND_DIR / f"{lock.stem}.tfstate").exists():
                out.append({"name": lock.stem, "resources": 0, "serial": None, "lock": json.loads(lock.read_text())})
    return out
