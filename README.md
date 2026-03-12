# vs-cli

a terminal-based code editor that fits in a single Python file.
no LSP, no plugins, no config files, no 400MB electron runtime.
just a text editor that runs in your terminal and doesn't make you want to quit your job.

```
 vs-cli  —  main.py                                                    
 EXPLORER           │   1 import os, sys, re                           
▸ src               │   2 from pathlib import Path                     
PY main.py          │   3                                              
PY utils.py         │   4 def main():                                  
{} config.json      │   5     print("hello")                          
MD README.md        │   6                                              
                    │                                                  
  INSERT  ⎇ main  saved — main.py          Ln 4, Col 1  PY  UTF-8    
```

---

## why does this exist

i needed an editor i could drop onto a server over SSH, open a file,
make a quick change, and get out. without installing node, without
configuring vim keybindings i'll forget in 3 days, without waiting for
a language server to warm up.

`nano` is fine but it looks like 1991. `vim` is powerful but requires
a PhD to exit. `micro` is close but it's a Go binary you have to
download. `vs-cli` is a single Python file that runs anywhere Python 3.10+
and `blessed` are available, which is basically everywhere.

it's not trying to replace your IDE. it's the editor you reach for
when you're already in the terminal and don't want to context-switch.

---

## installation

### requirements

- Python 3.10+ (uses `match/case`, so 3.9 won't work. upgrade.)
- `blessed` library

```bash
pip install blessed
```

that's it. there's no `setup.py`, no `pyproject.toml`, no package to install.
download the script, run it.

```bash
# download
curl -O https://example.com/vs_cli.py

# or clone if you want the whole repo
git clone https://github.com/you/vs-cli
cd vs-cli

# run
python vs_cli.py
python vs_cli.py /path/to/project
python vs_cli.py /path/to/file.py
```

### make it a proper command

if you want to call it as `vs-cli` from anywhere:

```bash
# put it somewhere on your PATH
cp vs_cli.py ~/.local/bin/vs-cli
chmod +x ~/.local/bin/vs-cli

# make sure ~/.local/bin is in PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# now you can just do:
vs-cli
vs-cli ~/projects/myapp
vs-cli ~/projects/myapp/src/main.py
```

on macOS, use `~/.local/bin` or `/usr/local/bin`. your call.

---

## usage

```
vs-cli [path]
```

- `path` is a file or a directory.
- if you pass a file, it opens that file directly and the explorer shows its parent directory.
- if you pass a directory, the explorer shows that directory and opens the first file it finds.
- if you pass nothing, it uses the current working directory.

### examples

```bash
# open current directory
vs-cli

# open a specific project
vs-cli ~/projects/django-app

# open a specific file
vs-cli ~/projects/django-app/settings.py

# pipe-friendly: no color output when stdout isn't a tty
NO_COLOR=1 vs-cli
```

---

## the interface

the layout is fixed. there's no way to resize the panels. if you need that,
you're using the wrong tool.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ title bar        filename, dirty marker (*)                              │
├──────────────┬───┬────┬─────────────────────────────────────────────────┤
│              │   │    │                                                  │
│  EXPLORER    │ │ │ ln │  editor content                                  │
│              │   │    │                                                  │
│  file tree   │   │    │  syntax-highlighted text                        │
│              │   │    │  cursor shown as inverted block                 │
│              │   │    │                                                  │
├──────────────┴───┴────┴─────────────────────────────────────────────────┤
│ ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ TERMINAL ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ │
│  scrollback output                                                       │
│  $ command input_                                                        │
├──────────────────────────────────────────────────────────────────────────┤
│ status bar   mode  branch  message           position  lang  encoding   │
└──────────────────────────────────────────────────────────────────────────┘
```

the terminal panel only appears when you open it with `F9` then `A`.
the rest of the layout is always visible.

---

## keybindings

### global (work everywhere)

| key | action |
|-----|--------|
| `F5` | focus file explorer |
| `F6` | focus editor |
| `Shift+F6` | open command palette |
| `F9` then `A` | open terminal panel |
| `F9` then `C` | close terminal panel |
| `Alt+S` | search in current file |
| `Alt+W` | navigate to folder path |
| `Ctrl+S` | save current file |
| `Ctrl+Q` | quit |

### editor

| key | action |
|-----|--------|
| `↑ ↓ ← →` | move cursor |
| `Ctrl+←` | jump word left |
| `Ctrl+→` | jump word right |
| `Home` | smart home (first press → indent, second press → col 0) |
| `End` | end of line |
| `PgUp / PgDn` | scroll fast (editor height - 2 rows) |
| `Enter` | newline with auto-indent |
| `Tab` | insert 2 spaces (no real tab characters, sorry not sorry) |
| `Backspace` | delete char left / merge lines |
| `Delete` | delete char right / merge lines |

### explorer

| key | action |
|-----|--------|
| `↑ ↓` | navigate file list |
| `Enter` | open file / toggle directory |
| `Backspace` | go to parent directory |

### terminal panel

| key | action |
|-----|--------|
| type normally | build up the command |
| `Enter` | run the command |
| `↑ ↓` | scroll through output |
| `Backspace` | delete last char of input |
| `Esc` | close terminal panel focus, back to editor |

### smart bar (search / path / command palette)

| key | action |
|-----|--------|
| type | filter results |
| `↑ ↓` | navigate results |
| `Enter` | confirm selection |
| `Esc` | close without doing anything |

---

## features

### syntax highlighting

supported languages:

| extension | language |
|-----------|----------|
| `.js` `.ts` `.jsx` `.tsx` `.mjs` `.cjs` | JavaScript / TypeScript |
| `.py` `.pyi` | Python |
| `.json` `.jsonc` | JSON |
| `.md` `.markdown` | Markdown |
| `.sh` `.bash` `.zsh` | Shell |
| `.html` `.htm` | HTML (no highlighting yet, just detected) |
| `.css` `.scss` | CSS (same) |
| `.rs` `.go` `.rb` `.cpp` `.c` `.h` | detected but no highlighting |

the highlighter is a hand-rolled tokenizer, not a grammar-based parser.
it handles the common cases well. it will do something wrong with
nested template literals or multi-line strings in some edge cases.
this is a known limitation and not something i'm going to apologize for.

what it highlights:
- **keywords** — blue. language-specific.
- **strings** — orange. handles `"double"`, `'single'`, and `` `backtick` `` quotes. respects escape sequences.
- **numbers** — soft green. integers, floats, hex, scientific notation.
- **comments** — gray. `//` line comments and `#` Python comments.
- **function names** — yellow. any identifier immediately followed by `(`.
- **type names** — teal. any identifier starting with an uppercase letter.
- **JSON keys** — blue.
- **Markdown headings** — blue + bold.
- **Markdown bullets** — teal.
- **Markdown inline code** — orange.
- **Markdown bold** — bold.

### file explorer

the explorer shows a live view of the filesystem.

- directories and files are sorted: directories first, then files, both alphabetically.
- certain directories are automatically hidden because no one wants to see them:
  `.git`, `__pycache__`, `node_modules`, `venv`, `.venv`, `dist`, `build`, `.idea`, `.vscode`, `.tox`, `.mypy_cache`, `.pytest_cache`
- dotfiles (anything starting with `.`) are also hidden.
- expand/collapse directories with `Enter`.
- the expanded state is remembered until you quit.
- `Backspace` navigates to the parent directory, even above the initial root.

### terminal panel

the terminal panel runs commands as subprocesses and captures their output.
it's not a real PTY. it doesn't handle interactive programs (no `vim`, `htop`,
`ssh`, `python -i`). it's for quick commands: `git status`, `ls`, `make`,
`python script.py`, `grep -r something .`.

- output is kept in a scrollback buffer of 2000 lines.
- commands timeout after 30 seconds. if you need longer, run it in a real terminal.
- the working directory is the explorer's current root. if you change root with
  `Alt+W`, the terminal follows.
- `F9` then `A` to open. `F9` then `C` to close. `Esc` to unfocus (panel stays open).

the chord system works like this: press `F9`, release it, then press `A` or `C`.
not a simultaneous chord. sequential. if you press `F9` and then something other
than `A` or `C`, the key is processed normally.

### command palette (`Shift+F6`)

available commands:

| command | does |
|---------|------|
| `save` | write the buffer to disk |
| `new` | open a new empty buffer (untitled.py) |
| `help` | show the keybindings screen |
| `git status` | run `git status --short` and show result in status bar |
| `git log` | run `git log --oneline -10` and show result in status bar |
| `exit` | quit |

type to filter. `↑↓` to navigate. `Enter` to run. `Esc` to cancel.

### search in file (`Alt+S`)

opens a search bar anchored to the top of the editor.
type your query. results show line numbers and matching lines.
`↑↓` to navigate. `Enter` to jump to the selected line.
`Esc` to cancel.

case-insensitive. substring match. no regex (yet).

### go to folder (`Alt+W`)

opens a path input pre-filled with the current explorer root.
edit it, press `Enter`. if the path is a valid directory, the
explorer navigates there. if not, you get an error in the status bar.
supports `~` expansion.

### auto-indent

when you press `Enter`, the new line is indented to match the current line's
indentation. it counts leading spaces and replicates them. it doesn't try to
be smart about brackets or colons. that's a job for a real language server.

### smart home

pressing `Home` on a line with leading whitespace moves the cursor to the
first non-whitespace character. pressing it again moves to column 0.
if you're already at the indent level, it goes to column 0 directly.
this is how most decent editors behave and i'm not going to justify it further.

### dirty file marker

when the buffer has unsaved changes, the title bar shows a `*` after the
filename. it goes away when you save. obvious, but it's there.

---

## color support

color is auto-detected at startup:

1. if `NO_COLOR` is set in the environment, no colors. ever.
2. if `COLORTERM` is `truecolor` or `24bit`, colors.
3. if `TERM` contains `256color` or `color`, or is `xterm`, `screen`, or `tmux`, colors.
4. if stdout is a tty, colors.
5. otherwise, no colors. the editor still works, it's just not pretty.

if your terminal shows garbage like `38B;5B;39m` in the text, it means the
terminal isn't interpreting ANSI escape codes. set `TERM=xterm-256color` before
running:

```bash
export TERM=xterm-256color
vs-cli
```

or just set `NO_COLOR=1` and use it without colors:

```bash
NO_COLOR=1 vs-cli
```

---

## architecture

the code is structured into these pieces:

```
vs_cli.py
│
├── color detection & ANSI helpers      ~30 lines
│   pure functions. no state.
│
├── syntax highlighting                 ~100 lines
│   _hl_code()   — JS and Python tokenizer
│   _hl_json()   — JSON regex + checks
│   _hl_md()     — Markdown regex
│   highlight()  — dispatcher with try/except guard
│
├── EditorState                         ~80 lines
│   the text buffer. list of strings + cursor + scroll.
│   load(), save(), insert(), backspace(), delete_fwd(),
│   newline(), move(), page(), home(), end(),
│   word_left(), word_right()
│
├── FileTree                            ~60 lines
│   flat list of nodes rebuilt on every toggle.
│   _open is a set of string paths for expanded dirs.
│   toggle(), go_up(), move(), current(), refresh()
│
├── TermPanel                           ~40 lines
│   deque of output lines. blocking subprocess.run().
│   run(), type(), bs(), up(), dn()
│
├── SmartBar                            ~40 lines
│   three modes: SEARCH, PATH, CMD.
│   open(), close(), active(), type(), bs(), nav(),
│   update(), hit_line(), hit_cmd()
│
└── VsCli                               ~300 lines
    owns everything, does rendering and input.
    render()          — builds one big string, writes once
    _draw_terminal()  — terminal panel section
    _draw_bar()       — floating input overlay
    _sync()           — viewport scroll adjustment
    handle()          — input dispatch with match/case
    _bar_confirm()    — confirm smart bar action
    _exec()           — execute command palette commands
    run()             — main loop
```

### rendering strategy

`render()` builds a list of strings, joins them, and writes to stdout in
one `sys.stdout.write()` call. this is intentional. multiple small writes
cause flickering because the terminal redraws between writes. one big write
is atomic enough that flicker is imperceptible at normal frame rates.

the frame rate is roughly 20fps (50ms timeout on `inkey()`). this is more
than enough for a text editor.

### why not curses

`curses` is in the standard library, which is nice. it's also annoying to
use correctly, has inconsistent behavior across platforms, and requires you
to think about windows and panels as objects. `blessed` gives you the ANSI
escape sequences you actually need without the abstraction overhead. and it
handles terminal capability detection (the `terminfo` stuff) so i don't have to.

### why not textual or rich

they're great libraries. they're also the wrong tool here. `textual` has
an event loop, widgets, CSS-like styling, reactivity. for a text editor
that needs to be a single script, that's too much machinery. the whole point
is simplicity.

---

## known limitations

- **no multiple open files / tabs.** one buffer at a time. open a different
  file via the explorer.

- **no undo.** i know. it's on the list. for now, Ctrl+Z in the terminal
  panel can sometimes save you, but the editor itself has no undo history.

- **no find & replace.** search (Alt+S) is read-only, jump-to-line only.

- **no clipboard integration.** there's no way to cut/copy/paste text between
  the editor and other applications. the terminal's own selection still works
  for reading, but the editor doesn't know about it.

- **terminal panel is not a PTY.** interactive programs don't work in it.
  `python -i`, `ssh`, `vim`, `top`, `less` — don't try. use a real terminal
  for those.

- **no config file.** keybindings, colors, tab size — all hardcoded.
  the tab size is 2 spaces. if you want 4, change the one line of code that
  says `ed.insert(' '); ed.insert(' ')`. i'm not adding a config system.

- **no syntax highlighting for C, Go, Rust, etc.** the tokenizer only handles
  JS/TS, Python, JSON, and Markdown. other file types are detected and opened
  but shown without colors.

- **highlighting breaks on some edge cases.** multi-line strings across
  multiple screen lines won't be colored correctly. triple-quoted Python
  strings that start on a visible line and end off-screen will look wrong.
  this is a fundamental limitation of line-by-line highlighting.

- **no line wrapping.** long lines are truncated at the viewport edge.
  horizontal scrolling works (the viewport follows the cursor), but there's
  no word wrap mode.

- **performance on huge files.** files with tens of thousands of lines are
  fine. files with hundreds of thousands of lines might make the cursor
  noticeably sluggish because the buffer is a plain Python list and
  operations like `list.insert()` are O(n). this is an acceptable trade-off
  for a script editor, not for opening kernel source trees.

---

## troubleshooting

### colors look wrong / show garbage characters

your terminal isn't handling ANSI escape codes correctly. try:

```bash
# option 1: tell it what kind of terminal it is
export TERM=xterm-256color
vs-cli

# option 2: disable color entirely
NO_COLOR=1 vs-cli

# check what blessed thinks about your terminal
python3 -c "
from blessed import Terminal
t = Terminal()
print('does_styling:', t.does_styling)
print('number_of_colors:', t.number_of_colors)
print('TERM:', __import__(\"os\").environ.get('TERM'))
"
```

### editor is blank / shows nothing

blessed probably failed to detect the terminal size. check:

```bash
echo $COLUMNS $LINES
tput cols; tput lines
```

if those return nothing, your terminal isn't reporting its size. try
resizing the window, or set them manually:

```bash
export COLUMNS=220
export LINES=50
vs-cli
```

### F9 chord isn't working

some terminals intercept F9 before it reaches the application, or map it
to something else. check if `F9` is being received:

```bash
python3 -c "
import os; os.environ.setdefault('TERM','xterm-256color')
from blessed import Terminal
t = Terminal()
print('press F9 then a key. Ctrl+C to exit.')
with t.raw():
    while True:
        k = t.inkey(timeout=5)
        if k: print(repr(k), repr(str(k)), k.name)
"
```

if F9 doesn't show up, your terminal is eating it. check your terminal's
keybinding settings.

### Shift+F6 isn't working

`Shift+F6` sends different escape sequences on different terminals.
vs-cli listens for `\x1b[17;2~` and `\x1b[1;2Q`. if your terminal sends
something else, look at what it sends (use the debug script above), find
the line in `handle()` that checks `raw in ('\x1b[17;2~', '\x1b[1;2Q')`,
and add your terminal's sequence.

### file shows as modified but i didn't change anything

some OS or editor tools modify files without the editor knowing. the
modified marker is set whenever you type anything in the buffer. it's
cleared on load and on save. if you open a file, don't touch it, and see
`*`, file an issue.

### terminal panel says "command not found" for something that works normally

the terminal panel inherits the environment from the Python process that
started vs-cli, but `PATH` might be different from your interactive shell.
check:

```bash
# in the terminal panel, type:
echo $PATH

# compare to your shell's PATH
# in your real terminal:
echo $PATH
```

if they differ, source your shell config first:

```bash
# start vs-cli with the right environment
bash -i -c 'vs-cli'
```

---

## contributing

the code is one file and it's meant to stay that way (roughly). a few
things i'd actually accept:

- real undo (a list of `(operation, args)` tuples, bounded to ~1000 entries)
- horizontal scrolling improvements
- additional syntax highlighting languages using the existing `_hl_code()` framework
- bug fixes for the highlighter's edge cases
- anything that makes the terminal panel more robust without adding a PTY dependency

a few things i will not accept:

- configuration files / settings system
- plugin architecture
- multiple tabs or split panes
- anything that requires adding a dependency beyond `blessed`
- LSP integration
- tree-sitter
- anything that makes the file longer than ~1200 lines

if you find a bug, describe it concisely and include the Python version,
OS, and terminal emulator. "it doesn't work" is not a bug report.

---

## license

do what you want with it.
if it deletes your files, that's your problem.
if it works great, that's my problem for not adding warranty disclaimers.

---

## acknowledgments

`blessed` by Jeff Quast does the actual terminal work.
the rest is just string concatenation.
