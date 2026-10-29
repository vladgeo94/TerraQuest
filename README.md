# 🏔️ TerraQuest

**A game for preparing for the _HashiCorp Certified: Terraform Associate (004)_ exam.**

TerraQuest runs on your own machine and opens in your browser. You work through 10 worlds, from absolute basics up to HCP Terraform. Each world has lessons, quizzes, **hands-on labs that run your real `terraform` binary**, and a boss fight. It ends with a timed **Final Boss** practice exam that follows the official exam objectives.

- 📘 **320 questions**: single choice, multiple choice, fill-in, and put-in-order
- 🛠️ **21 hands-on labs**: a real sandbox folder and a real terminal, graded automatically. No cloud account and no cost; labs use the `local`, `random` and `null` providers
- 🗄️ **A built-in remote state backend** with locking, so you can practise state migration and `force-unlock` for real
- ⭐ XP, levels, 1–3 stars per stage, a daily streak, and a **♻️ Respawn queue** that brings back the questions you got wrong
- 🏁 **Final Boss**: 57 questions in 60 minutes, spread across the 8 objectives, with a per-objective score breakdown

---

## About the exam

| | |
|---|---|
| **Name** | HashiCorp Certified: Terraform Associate (004) |
| **Replaced** | Terraform Associate (003), retired on January 8, 2026 |
| **Format** | Multiple choice / multiple answer, about 1 hour, online proctored |
| **Terraform version tested** | 1.12 |
| **Official objectives** | [Exam content list](https://developer.hashicorp.com/terraform/tutorials/certification-004/associate-review-004) |

The worlds map to the official objectives like this:

| World | Objective |
|---|---|
| 0 🏕️ Bootcamp | Basics (no exam objective; start here if you're new) |
| 1 🏛️ IaC Foundations | 1. Infrastructure as Code (IaC) with Terraform |
| 2 🔌 Providers & State | 2. Terraform fundamentals |
| 3 ⚙️ The Core Workflow | 3. Core Terraform workflow |
| 4 🧱 Configuration I | 4a–4d. Resources, data sources, references, variables & outputs, complex types |
| 5 🧪 Configuration II | 4e–4h. Expressions & functions, dependencies, custom conditions, sensitive data & Vault |
| 6 📦 Modules | 5. Terraform modules |
| 7 🗄️ State Mastery | 6. Terraform state management (plus CLI workspaces) |
| 8 🔧 Maintenance Ops | 7. Maintain infrastructure with Terraform |
| 9 ☁️ HCP Terraform | 8. HCP Terraform (concepts and quizzes; labs can't log in to HCP for you) |
| 🏁 Final Boss | Everything: a timed practice exam |

---

## Requirements

Works on **Linux, macOS and Windows**.

| Need | Why | Install |
|---|---|---|
| **Python 3.11+** | Runs the game server (standard library only, no `pip install`) | Arch/CachyOS: `sudo pacman -S python` · Debian/Ubuntu: `sudo apt install python3` · macOS: `brew install python` · Windows: [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12` |
| **Terraform** | Hands-on labs run your real `terraform` | Arch/CachyOS: `sudo pacman -S terraform` · macOS: `brew install hashicorp/tap/terraform` · Windows: `winget install Hashicorp.Terraform` · others: [install guide](https://developer.hashicorp.com/terraform/install) |
| **Git** | To download the game | Usually preinstalled; otherwise your package manager |
| A web browser | The game UI | Any modern browser |
| Internet (first lab only) | Terraform downloads the `local`/`random` providers **once** and caches them | |

Any Terraform 1.5 or newer works for every lab. 1.12+ is closest to what the exam tests.

---

## Get it and start the game

```bash
git clone https://github.com/vladgeo94/TerraQuest.git
cd TerraQuest
```

Then start it:

| System | Command |
|---|---|
| Linux / macOS | `./terraquest.sh` |
| Windows | double-click `terraquest.cmd`, or run `terraquest.cmd` in a terminal |
| Anywhere (same thing) | `python3 terraquest.py` (on Windows: `py terraquest.py`) |

The launcher checks Python and Terraform, starts the server at **http://127.0.0.1:8080**, and opens your browser. Leave the terminal open while you play. **Ctrl+C** stops the server, and your progress is saved automatically.

To get updates later: `git pull` in the `TerraQuest` folder, then restart the game.

### Options

These work with any of the launchers above:

```bash
./terraquest.sh --port 8081        # use another port
./terraquest.sh --no-browser       # don't open the browser automatically
./terraquest.sh --check            # validate the content files and exit
./terraquest.sh --install-desktop  # Linux only: add "TerraQuest" to your application menu
```

If the script isn't executable: `chmod +x terraquest.sh`.

### Progress is per machine
Progress is saved on the computer you play on (see [Where your data lives](#where-your-data-lives)). To continue on another machine, copy `progress.json` from the old machine's data folder to the same place on the new one.

---

## How to play

### The map
Worlds unlock one after another. Inside a world, stages unlock in order:

- **📘 Lesson:** read a short lesson, then answer questions. You need **70%** to pass.
- **🛠️ Lab:** hands-on Terraform in a real folder (see below).
- **👹 Boss:** a harder mixed quiz. You need **80%** to pass, and beating it unlocks the next world.

**Stars:** ★★★ = perfect and no hints · ★★ = 85% or more · ★ = passed. For labs: ★★★ = passed on the first check with no hints · ★★ = up to 3 checks and 1 hint · ★ = passed.

### XP
Every reward is paid **once**, so replaying a stage can't farm XP:

| Source | XP |
|---|---|
| A question answered correctly for the first time (anywhere: lesson, Respawn or exam) | 10 (20 for boss questions) |
| Each new star on a stage (going from ★ to ★★★ later pays the 2 missing stars) | 10 per star |
| Completing a lab for the first time | 50 |
| Passing the Final Boss for the first time | 100 |

So a 6-question lesson is worth at most 6 × 10 + 3 stars × 10 = 90 XP. Replaying still updates your stars, best score and Respawn queue.

**↺ Reset lab** clears that lab's stars, so you can earn them again, but the XP you already earned stays. Earning the stars back pays nothing extra; only stars you never had before pay XP.

### Labs
Each lab is a real folder at `labs/<world>_<stage>/` inside your [data folder](#where-your-data-lives).

- **Left panel:** the lesson, your mission, a checklist, hints, and (in some labs) **🎭 Events** that simulate things happening outside Terraform, like a teammate locking state or someone editing a file by hand.
- **Editor:** tabs for every file. `Tab` indents, **Ctrl+S** saves, and **＋ New file** creates files, including in sub-folders like `modules/greeter/main.tf`. State files and logs open read-only, so you can look inside `terraform.tfstate`.
- **Terminal:** type real commands, for example `terraform init`, `terraform plan -out=tfplan`, or `terraform state list`.
  - Files are **saved automatically** before each command.
  - `apply`/`destroy` get `-auto-approve` added (there's no interactive prompt), and `force-unlock` gets `-force`.
  - Environment variables work in front of a command: `TF_LOG=DEBUG TF_LOG_PATH=tf.log terraform plan`, `TF_VAR_name=x terraform apply`.
  - `terraform console` works through a pipe: `echo 'upper("hi")' | terraform console`.
  - ↑/↓ cycle through your command history.
- **Check my work** grades the lab by reading the real state, files and plan output.
- **↺ Reset lab** restores the starting files and state.

You can also open the lab folder in your own editor or terminal. Run `terraform` there directly and then click **Check my work** in the game.

### ♻️ Respawn queue
Every question you get wrong goes into the Respawn queue (top bar). A question leaves the queue once you answer it correctly **twice in a row**.

### 🏁 Final Boss (practice exam)
It unlocks after you beat every world boss, or right away in practice mode.

- 57 questions and a 60-minute timer, with no feedback until you submit, like the real exam
- Flag questions and jump around using the question grid
- Afterwards you get your score, a breakdown per objective, and a review of every wrong answer with an explanation
- Aim for **80% or higher several times in a row** before booking the real exam. HashiCorp doesn't publish the passing score, so the game uses 70% as its pass mark.

### ⚙️ Settings
- **Practice mode:** unlock everything, which is handy for revision. Stages you haven't reached in normal progress are marked 🧪 and are **practice runs**: you can play them fully, but no XP, stars, Respawn changes or exam bonus are saved. Stages you've already unlocked normally keep counting as usual.
- **Reload content:** picks up edits to the question files without restarting the server
- **Reset progress**, or reset progress **and** delete all labs

---

## Where your data lives

| What | Path |
|---|---|
The data folder is `~/.local/share/terraquest/` on Linux and macOS, and `%LOCALAPPDATA%\TerraQuest\` on Windows. Inside it:

| What | Path |
|---|---|
| Progress (XP, stars, history, Respawn queue) | `progress.json` |
| Lab sandboxes | `labs/` |
| Provider cache, shared by all labs | `plugin-cache/` |
| The game's HTTP backend (remote state for the World 7 labs) | `http-backend/` |

Set `TERRAQUEST_DATA=/some/other/dir` to keep everything somewhere else.

To uninstall completely: delete the `TerraQuest/` folder and the data folder, and run `./terraquest.sh --uninstall-desktop` if you installed the menu entry.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Port 8080 is already in use` | TerraQuest is probably already running, so just open http://127.0.0.1:8080. Otherwise use `./terraquest.sh --port 8081`. |
| The first lab hangs or fails at `terraform init` | The first `init` downloads providers and needs internet. Later labs use the cache. |
| `terraform not found` | Install Terraform (see [Requirements](#requirements)), make sure it's on your PATH, then restart the game. |
| A lab is in a weird state | Click **↺ Reset lab**. |
| A World 7 lab says the backend is unreachable | The lab files point at the game's own server (`http://127.0.0.1:<port>/tfstate/...`). If you changed the port, **reset the lab** so the files pick up the new address. |
| You edited a question file and the game shows an error | Run `./terraquest.sh --check`. It names the file and line with the problem. |
| The browser didn't open | Open http://127.0.0.1:8080 yourself. |
| Windows: `python` opens the Microsoft Store | Install Python from python.org (tick "Add to PATH"), or use `py terraquest.py`. |

---

## Project layout

```
TerraQuest/
├── terraquest.py          # launcher (all platforms)
├── terraquest.sh          # Linux/macOS wrapper (+ --install-desktop)
├── terraquest.cmd         # Windows wrapper
├── server/
│   ├── app.py             # HTTP server: UI, game API, Terraform HTTP state backend
│   ├── content.py         # loads and grades questions from TOML
│   ├── labs.py            # lab sandboxes, guarded terraform runner, checks
│   ├── progress.py        # XP, stars, streaks, Respawn queue
│   └── paths.py
├── web/                   # single-page UI (plain HTML/CSS/JS, no build step)
└── content/worlds/*.toml  # all lessons, questions and labs
```

Want to add your own questions or labs? See [CONTENT_GUIDE.md](CONTENT_GUIDE.md).

> TerraQuest is an independent study tool. It isn't affiliated with or endorsed by HashiCorp. Always check the [official exam page](https://developer.hashicorp.com/certifications/terraform-associate) for current exam details.

## License

GPL-3.0. See [LICENSE](LICENSE).
