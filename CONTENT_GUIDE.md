# Content guide

All game content lives in `content/worlds/*.toml`, one file per world. Files are loaded in `order`. After editing, click **⚙️ Settings → Reload content**, or restart the game. To validate your changes:

```bash
./terraquest.sh --check
```

Tip: use TOML literal strings (`'''...'''`) for lessons and HCL, so backslashes and `${}` need no escaping.

## World

```toml
id = "w10"                     # unique, stable (progress is keyed on it)
order = 10                     # position on the map
title = "My World"
subtitle = "One-line description"
objective = "Objective 4 · Terraform configuration"   # label on the map
objective_code = "4"           # default objective for questions; "0" keeps them out of the Final Boss exam
icon = "🧩"
```

The **last stage with `boss = true`** (or the last stage, if there's no boss) must be completed to unlock the next world.

## Quiz stage

```toml
[[stages]]
id = "s1"                      # unique within the world, stable
title = "Stage title"
boss = false                   # true = 80% pass mark, questions shuffled
pass = 0.7                     # optional override
lesson = '''
Markdown: headings, **bold**, `code`, lists, > callouts, | tables |, and ```hcl fenced code.
'''

[[stages.questions]]
type = "single"                # single | multi | fill | order
q = "Question text (inline markdown allowed)"
code = '''optional HCL shown under the question'''
options = ["A", "B", "C"]
answer = 1                     # index into options
obj = "4c"                     # official sub-objective; drives the Final Boss weighting and breakdown
hint = "Optional hint (using it costs a star)"
explain = "Shown after answering (markdown)"
docs = "https://developer.hashicorp.com/..."   # optional link
```

| type | answer format |
|---|---|
| `single` | `answer = 2` |
| `multi` | `answer = [0, 2]`; the UI says "Choose N" |
| `fill` | `answer = ["accepted", "also accepted"]`; whitespace is collapsed, matching is case-insensitive unless `case_sensitive = true` |
| `order` | `items = ["first", "second", "third"]` in the **correct** order; the UI shuffles them |

Options for `single`/`multi` are shuffled every time a question is shown. Set `shuffle_options = false` to keep the written order. This happens automatically when an option mentions "above", as in "All of the above".

Questions get stable IDs from their position (`w4.s3.2`). Give a question an explicit `id = "..."` if you plan to reorder questions often, so Respawn history stays attached.

## Lab stage

```toml
[[stages]]
id = "lab1"
title = "Lab: Something"
lesson = '''Intro markdown'''

[stages.lab]
goal = '''Markdown mission'''
suggested = ["terraform init", "terraform apply"]   # quick-command buttons
setup = ["terraform init", "terraform apply"]       # optional: run when the lab opens or resets
reset_backend = ["state-name"]                      # optional: wipe game backend states on reset
backend_panel = true                                # show the HTTP backend panel
hints = ["first hint", "second hint"]
solution = '''optional markdown solution (viewing it caps the lab at 1 star)'''

[stages.lab.files]                                  # starter files (sub-folders allowed)
"main.tf" = '''...'''
"modules/x/main.tf" = '''...'''

[stages.lab.post_setup_files]                       # optional: written AFTER setup commands
"main.tf" = '''...'''

[[stages.lab.actions]]                              # optional "🎭 Events" buttons
id = "drift"
label = "Someone edits the file"
type = "write_file"                                 # write_file | delete_file | backend_lock
path = "config.txt"
content = "changed\n"

[[stages.lab.checks]]
type = "resource"
address = "local_file.hello"
msg = "Shown in the checklist"
```

`{{BASE_URL}}` in lab files is replaced with the game server's URL, for example `http://127.0.0.1:8080`. Use it to point the `http` backend at `{{BASE_URL}}/tfstate/<name>`.

### Check types

| type | fields | passes when |
|---|---|---|
| `initialized` | none | `.terraform/` exists |
| `lockfile` | `provider` | `.terraform.lock.hcl` contains the text |
| `validate_ok` / `fmt_ok` | none | `terraform validate` / `terraform fmt -check -recursive` succeed |
| `config_regex` / `config_not_regex` | `pattern` | regex does / doesn't match all `.tf` files concatenated |
| `file_exists` / `file_absent` | `path` | |
| `file_contains` | `path`, `text` | |
| `file_regex` | `path`, `pattern` | |
| `resource` / `no_resource` | `address` | address (including `module.x.…`, `data.…`, `["key"]`) is / isn't in state |
| `resource_count` | `rtype`, `count`, `at_least?`, `mode?` | number of managed resources of that type |
| `state_empty` | none | no managed resources in state |
| `attr` | `address`, `attr`, `equals` or `regex` | attribute in state (`attr` supports `a.b[0]`) |
| `output` | `name`, `equals?`, `regex?`, `sensitive?` | root output in state |
| `no_changes` | none | `terraform plan -detailed-exitcode` returns 0 |
| `command_ok` / `command_fails` | `cmd`, `output_regex?` | runs the command in the lab folder |
| `snapshot_same` | `was`, `address`, `attr`, `expect_change?` | compares against state captured after `setup` |
| `history` | `pattern` | regex matches the commands the player ran in the game terminal |
| `backend_state` | `name`, `min_resources?` | the game's HTTP backend holds that state |
| `backend_unlocked` | `name` | no lock on that state |
| `no_local_state` | none | local `terraform.tfstate` holds no resources |
| `workspace_exists` | `name` | listed by `terraform workspace list` |
| `workspace_resource` | `workspace` | local `terraform.tfstate.d/<ws>/` has resources |
