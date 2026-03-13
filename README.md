# vs-cli
<img width="165" height="160" alt="Screenshot_2026-03-12_21-22-05" src="https://github.com/user-attachments/assets/4e4c58d5-b43c-4615-b805-d42c378dff95" />

> A terminal code editor that doesn't suck (much). One dependency. Runs anywhere Python runs.

```
pip install blessed
python vs_cli.py [file or directory]
```

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![dependency: blessed](https://img.shields.io/badge/dependency-blessed-green.svg)](https://pypi.org/project/blessed/)
[![license: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)]()

---

## Table of Contents

- [What Is This?](#what-is-this)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Interface Layout](#interface-layout)
- [Keyboard Shortcuts](#keyboard-shortcuts)
  - [Global](#global)
  - [Editor](#editor)
  - [Explorer](#explorer)
  - [Terminal Panel](#terminal-panel)
  - [SmartBar (all modes)](#smartbar-all-modes)
- [Features](#features)
  - [Syntax Highlighting](#syntax-highlighting)
  - [Undo / Redo](#undo--redo)
  - [Bracket Auto-Close & Matching](#bracket-auto-close--matching)
  - [Smart Indentation Detection](#smart-indentation-detection)
  - [Smart Home Key](#smart-home-key)
  - [Word Jump](#word-jump)
  - [Git Gutter Indicators](#git-gutter-indicators)
  - [Quick Open (Ctrl+P)](#quick-open-ctrlp)
  - [Global Grep (Ctrl+F)](#global-grep-ctrlf)
  - [Find & Replace (Alt+R)](#find--replace-altr)
  - [Outline View (Ctrl+O)](#outline-view-ctrlo)
  - [Sticky Scroll](#sticky-scroll)
  - [Zen Mode (F11)](#zen-mode-f11)
  - [Integrated Terminal Panel](#integrated-terminal-panel)
  - [Command Palette](#command-palette)
  - [File Explorer](#file-explorer)
- [SmartBar Deep Dive](#smartbar-deep-dive)
- [Supported Languages & File Icons](#supported-languages--file-icons)
- [Color & Theme System](#color--theme-system)
- [Architecture Overview](#architecture-overview)
  - [EditorState](#editorstate)
  - [FileTree](#filetree)
  - [TermPanel](#termpanel)
  - [SmartBar](#smartbar)
  - [VsCli (Main)](#vscli-main)
- [Rendering Engine](#rendering-engine)
- [Known Limitations](#known-limitations)
- [Configuration & Customization](#configuration--customization)
- [FAQ](#faq)
- [Contributing](#contributing)

---

## What Is This?

`vs-cli` is a single-file, terminal-based code editor written in Python. It takes visual inspiration from VS Code — sidebar file explorer, git gutter, status bar, command palette, integrated terminal — and squeezes all of it into roughly 700 lines of pure Python with exactly one third-party dependency: [`blessed`](https://pypi.org/project/blessed/), a mature terminal control library.

It is designed for situations where you need a real editor but can't or don't want to run a full GUI:

- SSH sessions on remote servers
- Docker containers
- CI/CD pipelines doing quick file edits
- Minimal Linux environments without X11
- Anywhere Vim feels like overkill and `nano` feels like underwhelm

It is **not** designed to replace VS Code, Neovim, or Emacs for your daily driver. It has no plugin system, no LSP support, no multiple cursors, and no project-level configuration. It is a sharp, minimal tool for a specific job.

---

## Installation

**Requirements:** Python 3.10 or newer (uses `match` statements).

```bash
pip install blessed
```

That's it. No other dependencies. Download or clone the script and run it.

```bash
# clone
git clone https://github.com/yourname/vs-cli
cd vs-cli

# or just grab the single file
curl -O https://raw.githubusercontent.com/yourname/vs-cli/main/vs_cli.py
```

**Verify it works:**

```bash
python vs_cli.py .        # opens current directory
```

---

## Quick Start

```bash
# Open a directory (file explorer on the left)
python vs_cli.py /path/to/project

# Open a specific file directly
python vs_cli.py myfile.py

# Open current directory
python vs_cli.py
```

On launch, if a directory is given, vs-cli opens the first file it finds in the explorer automatically. You're immediately in editor mode and can start typing.

**The five things you need to know to survive:**

| Action | Key |
|---|---|
| Save | `Ctrl+S` |
| Quit | `Ctrl+Q` |
| Open file quickly | `Ctrl+P` |
| Switch to file explorer | `F5` |
| Switch back to editor | `F6` |

---

## Interface Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  vs-cli  —  main.py*                                             │  ← title bar
├──────────┬─┬──────┬──────────────────────────────────────────────┤
│ EXPLORER │g│      │  1  import os                                │
│          │u│  ln  │  2  import sys                               │
│ ▸ src    │t│  nm  │  3                                           │  ← editor area
│   main.py│t│  bs  │  4  def main():                              │
│   utils.py│e│      │  5      pass                               │
│ ▸ tests  │r│      │  6                                           │
│          │ │      │                                              │
├──────────┴─┴──────┴──────────────────────────────────────────────┤
│ ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ TERMINAL ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ │  ← terminal (optional)
│   $ python main.py                                               │
│   Hello, world                                                   │
│ $ _                                                              │
├──────────────────────────────────────────────────────────────────┤
│  INSERT  ⎇ main  saved — main.py    Ln 4, Col 1  4spc  PY  UTF-8│  ← status bar
└──────────────────────────────────────────────────────────────────┘
```

**Columns (left to right):**

- **Explorer (26 cols)** — file tree with expand/collapse. Hidden in zen mode.
- **Git gutter (1 col)** — colored indicator per line. Hidden in zen mode.
- **Divider (1 col)** — visual separator.
- **Line numbers (5 cols)** — current line is highlighted bold.
- **Editor area** — the rest of the terminal width.

**Status bar (bottom row):**

- Mode: `INSERT` / `EXPLORE` / `TERMINAL`
- Branch: `⎇ main` (static placeholder — see [Known Limitations](#known-limitations))
- Last message (saved, error, info)
- Cursor position: `Ln N, Col N`
- Indent info: `4spc` or `tab`
- Language: `PY`, `JS`, `TS`, `JSON`, etc.
- Encoding: always `UTF-8`

---

## Keyboard Shortcuts

### Global

These work regardless of which panel has focus.

| Key | Action |
|---|---|
| `F5` | Focus file explorer |
| `F6` | Focus editor |
| `Shift+F6` | Open command palette |
| `F11` | Toggle zen mode |
| `F9` → `A` | Open terminal panel |
| `F9` → `C` | Close terminal panel |
| `Ctrl+S` | Save current file |
| `Ctrl+Q` | Quit |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+P` | Quick open (fuzzy file picker) |
| `Ctrl+F` | Global grep across project |
| `Ctrl+O` | Outline / symbol search |
| `Alt+S` | Search in current file |
| `Alt+W` | Go to folder (change explorer root) |
| `Alt+R` | Find and replace in current file |

### Editor

| Key | Action |
|---|---|
| `↑ ↓ ← →` | Move cursor |
| `Ctrl+←` | Jump word left |
| `Ctrl+→` | Jump word right |
| `Home` | Smart home (indent → column 0 → indent) |
| `End` | Move to end of line |
| `Page Up / Page Down` | Scroll by page |
| `Enter` | New line with smart indent |
| `Tab` | Insert indent (spaces or tab, auto-detected) |
| `Backspace` | Delete character left (or paired bracket) |
| `Delete` | Delete character right |

### Explorer

| Key | Action |
|---|---|
| `↑ / ↓` | Navigate file list |
| `Enter` | Open file / expand or collapse directory |
| `Backspace` | Navigate to parent directory |

### Terminal Panel

| Key | Action |
|---|---|
| `Enter` | Execute typed command |
| `Backspace` | Delete last character |
| `↑ / ↓` | Scroll terminal output |
| `Esc` | Return focus to editor |

### SmartBar (all modes)

| Key | Action |
|---|---|
| Type | Filter / search |
| `↑ / ↓` | Navigate results |
| `Enter` | Confirm selection |
| `Esc` | Close SmartBar |
| `Tab` | (Find+Replace only) Switch between find / replace fields |

---

## Features

### Syntax Highlighting

vs-cli ships a hand-rolled tokenizer — not a real parser, but it handles roughly 95% of real-world code correctly. The other 5% just loses color, which is fine.

**Supported languages:**

| Language | What gets highlighted |
|---|---|
| Python | Keywords, types, function names, strings, numbers, `#` comments |
| JavaScript / TypeScript | Keywords, types, function names, strings, numbers, `//` comments |
| JSON | Keys, string values, numeric / boolean / null values |
| Markdown | Headings (`#`), bullet lists, inline code, bold |
| Others (sh, html, css, rs, go…) | No highlighting — file type detected for icon/status bar only |

**Color palette (256-color):**

| Token type | Color |
|---|---|
| Keywords | Cyan (`#39`) |
| Strings | Orange (`#214`) |
| Numbers | Light green (`#150`) |
| Comments | Gray (`#242`) |
| Function names | Yellow (`#221`) |
| Type names (PascalCase) | Green (`#78`) |
| Markdown headings | Cyan (`#39`) |
| Bracket match | Yellow on dark orange |

Color output is automatically disabled if `NO_COLOR` is set, if stdout is not a TTY, or if the terminal doesn't advertise 256-color support.

### Undo / Redo

The undo system uses a snapshot stack stored in a `deque` capped at 500 entries. Before every destructive operation (`insert`, `backspace`, `delete_fwd`, `newline`, `tab`), the editor takes a snapshot of the full line buffer plus cursor position.

**Deduplication:** If the same snapshot would be added twice consecutively (e.g., holding a key down), it is skipped. This prevents the undo stack from filling up with thousands of identical states during key repetition.

**Redo:** Any new edit after an undo clears the redo stack — standard behavior. Redo only works when you have undone something without making new edits in between.

| Key | Action |
|---|---|
| `Ctrl+Z` | Undo last change |
| `Ctrl+Y` | Redo |

The undo stack is per-buffer and is cleared on file open. There is no persistent undo history across sessions.

### Bracket Auto-Close & Matching

**Auto-close:** When you type an opening bracket or quote, the closing counterpart is inserted automatically and the cursor is placed between them.

| Type | Inserted | Cursor ends up |
|---|---|---|
| `(` | `()` | between the parens |
| `[` | `[]` | between the brackets |
| `{` | `{}` | between the braces |
| `"` | `""` | between the quotes |
| `'` | `''` | between the quotes |
| `` ` `` | ` `` ` | between the backticks |

**Skip-over:** If the cursor sits directly on a closing character that was auto-inserted, typing that character again moves the cursor past it instead of inserting a duplicate.

**Auto-delete pair:** Pressing Backspace on an opening character when the cursor is directly between a matched pair deletes both characters simultaneously.

**Visual matching:** When the cursor rests on any bracket character (`(`, `)`, `[`, `]`, `{`, `}`), the matching bracket is highlighted in yellow-on-brown. The search is depth-aware — nested brackets are handled correctly across multiple lines.

### Smart Indentation Detection

On file load, vs-cli scans the first 200 lines to detect whether the file uses tabs or spaces for indentation. For spaces, it finds the most common indent width (typically 2 or 4).

The detected settings appear in the status bar (`4spc` or `tab`) and apply to:

- `Tab` key — inserts the correct number of spaces or a literal tab
- `Enter` key — continues the current line's indentation on the new line

**Auto-indent on Enter:** After a line ending in `:` (Python block opener) or `{` (C-style opener), the next line is automatically indented one level deeper.

### Smart Home Key

The `Home` key cycles through two positions:

1. If cursor is **not** at the first non-whitespace character → move there
2. If cursor **is** at the first non-whitespace character → move to column 0

This lets you quickly toggle between the indented code start and the absolute line start, matching the behavior found in VS Code and most modern editors.

### Word Jump

`Ctrl+←` and `Ctrl+→` move the cursor by word boundaries. Alphanumeric characters (`a-z`, `A-Z`, `0-9`, `_`) form words; punctuation and whitespace act as delimiters.

### Git Gutter Indicators

On file open and on every save, vs-cli runs `git diff --unified=0` against the current file and parses the unified diff output to map which lines have changed relative to the last commit.

Changes are shown as a single colored character in the 1-column gutter between the explorer and line numbers:

| Indicator | Color | Meaning |
|---|---|---|
| `▌` | Green | Line was added (not in last commit) |
| `▌` | Yellow | Line was modified |
| `▾` | Red | A line was deleted just below this position |

The gutter is silently skipped (stays blank) if the file is not in a git repository, if `git` is not on `$PATH`, or if the diff command times out (3 second timeout).

### Quick Open (`Ctrl+P`)

Opens a floating SmartBar. As you type, it performs a fuzzy filename search across the entire project tree (up to 2000 files scanned, 50 results shown at most).

The fuzzy match requires every character you type to appear somewhere in the filename. For example, typing `mnpy` would match `main.py`. The match is against the filename only, not the full path.

Navigate results with `↑ / ↓`, open the selected file with `Enter`.

Directories listed in `_SKIP` (`.git`, `node_modules`, `__pycache__`, `venv`, and others) are excluded from the search.

### Global Grep (`Ctrl+F`)

Invokes the system `grep -rn` binary to search all text files in the project for the query string. Results appear in the format `filename:line_number:content`, up to 100 results, with a 10-second timeout.

Selecting a result and pressing `Enter` opens the file and jumps directly to that line number.

Requires `grep` on `$PATH`. Falls back gracefully with empty results if grep is unavailable.

### Find & Replace (`Alt+R`)

Opens a two-field SmartBar. Use `Tab` to switch between the **find** field and the **replace** field.

Pressing `Enter` performs a **replace-all** — every occurrence of the find string in the current buffer is replaced in a single operation. The replacement is case-sensitive and plain-string only (no regular expressions). The operation is a single undoable step.

The results panel shows a live preview of all matching lines as you type in the find field.

### Outline View (`Ctrl+O`)

Scans the current file for function and class definitions and presents them as a navigable list. Supports Python and JavaScript/TypeScript.

**Python:** Detects `def` and `class` keywords at any indentation level. Nesting is reflected with `⬢` for functions and `⬡` for classes, indented proportionally.

**JavaScript/TypeScript:** Detects `function name()`, `const name = () =>` / `const name = async () =>`, and `class Name`.

Select a symbol and press `Enter` to jump directly to its definition line.

### Sticky Scroll

When the editor is scrolled down past a function or class definition, that definition line is pinned to the top row of the editor area. This shows you which function body you are currently inside without requiring you to scroll back up — the same feature VS Code calls "sticky scroll."

Works for Python (`def`, `class`) and JavaScript/TypeScript (`function`, `class`, `async function`). Disabled in zen mode and on the help screen.

### Zen Mode (`F11`)

Hides the sidebar, git gutter, and status bar. The editor takes the full terminal width. Visual noise is minimized. The title bar remains visible and shows `[zen]`.

Toggle on and off with `F11` at any time. All other features continue to work normally in zen mode.

### Integrated Terminal Panel

The terminal panel opens at the bottom of the screen (12 rows tall, configurable via `TERM_H`). Commands are run via blocking `subprocess.run()` with a 30-second timeout.

This is **not** a PTY. Practical consequences:

| Works | Does not work |
|---|---|
| `ls`, `pwd`, `cat`, `grep` | `vim`, `nano`, `htop` |
| `python script.py` (non-interactive) | `python` REPL |
| `git status`, `git log`, `git diff` | `ssh` sessions |
| `npm test`, `pytest`, `make` | `less`, `more`, `man` |
| `pip install`, `npm install` | `top`, `watch` |

The panel maintains a scrollback buffer of 2000 lines. Use `↑ / ↓` to scroll through output.

The working directory is the project root and updates when you navigate to a different folder via `Alt+W`.

**Open:** `F9` then `A`  
**Close:** `F9` then `C`  
**Return focus to editor:** `Esc`

### Command Palette

Accessible via `Shift+F6`. Provides a searchable list of built-in commands:

| Command | Description |
|---|---|
| `save` | Write buffer to disk |
| `new` | Create empty buffer |
| `help` | Show keybinding reference screen |
| `outline` | Open symbol outline |
| `git status` | Show short git status in status bar |
| `git log` | Show last 10 commits (one-line format) in status bar |
| `zen` | Toggle zen mode |
| `exit` | Quit |

Type to filter the list. Navigate with `↑ / ↓`, run with `Enter`.

### File Explorer

The left-side panel shows a recursive file tree starting from the project root. Directories sort before files; all names are sorted alphabetically within their group.

**Hidden automatically:** `.git`, `__pycache__`, `.DS_Store`, `node_modules`, `.pytest_cache`, `.mypy_cache`, `venv`, `.venv`, `.tox`, `.idea`, `.vscode`, `dist`, `build`, and any file/directory whose name starts with `.`.

**Navigation:**

- `↑ / ↓` to move through the list
- `Enter` on a directory to expand or collapse it
- `Enter` on a file to open it in the editor (also switches focus to editor)
- `Backspace` to navigate to the parent directory

Switch to the explorer with `F5`; return to editor with `F6`.

---

## SmartBar Deep Dive

The SmartBar is the unified floating input widget used for all modal interactions. It renders as a rounded box (`╭─╮`) overlaid on the editor, with a title, input field, results list, and hint line at the bottom.

There are seven modes:

| Mode constant | Trigger | What it does |
|---|---|---|
| `SEARCH` | `Alt+S` | Incremental search in current file |
| `PATH` | `Alt+W` | Navigate to a directory by path |
| `CMD` | `Shift+F6` | Command palette |
| `OPEN` | `Ctrl+P` | Fuzzy file quick-open |
| `GREP` | `Ctrl+F` | Global grep across project |
| `REPLACE` | `Alt+R` | Find and replace (two-field input) |
| `OUTLINE` | `Ctrl+O` | Symbol / function outline |

All modes share the same keyboard interface: type to filter, `↑ / ↓` to navigate results, `Enter` to confirm, `Esc` to dismiss without action.

`REPLACE` mode is the only two-field mode — `Tab` switches between the find and replace inputs, each with its own cursor indicator.

---

## Supported Languages & File Icons

### Language Detection

Language is determined strictly by file extension:

| Extensions | Language ID | Highlighting |
|---|---|---|
| `.js`, `.ts`, `.jsx`, `.tsx`, `.mjs`, `.cjs` | `js` | Yes |
| `.py`, `.pyi` | `py` | Yes |
| `.json`, `.jsonc` | `json` | Yes |
| `.md`, `.markdown` | `md` | Yes |
| `.sh`, `.bash`, `.zsh` | `sh` | No |
| `.html`, `.htm` | `html` | No |
| `.css`, `.scss` | `css` | No |
| `.rs` | `rs` | No |
| `.go` | `go` | No |
| `.rb` | `rb` | No |
| `.cpp`, `.c`, `.h` | `cpp` / `c` | No |
| `.toml` | `toml` | No |
| `.yaml`, `.yml` | `yaml` | No |

Files with unrecognized extensions are treated as plain text.

### File Icons (in explorer)

Three-character labels shown before filenames in the explorer sidebar:

```
.js  → JS    .ts  → TS    .py  → PY    .rs  → RS
.go  → GO    .rb  → RB    .c   → C     .cpp → C+
.h   → H     .json→ {}    .md  → MD    .css → CS
.html→ HT    .sh  → SH    .txt → TX    .yml → YM
.env → EN    .toml→ TM    .lock→ LK
```

Directories show `▸ ` when collapsed and `▾ ` when expanded.

---

## Color & Theme System

vs-cli uses ANSI 256-color escape codes. Color output is automatically detected and disabled gracefully if not supported.

**Detection logic (evaluated in order):**

1. `NO_COLOR` environment variable is set → disable all color
2. `COLORTERM=truecolor` or `COLORTERM=24bit` → enable
3. `$TERM` contains `256color` → enable
4. `$TERM` is `xterm`, `screen`, or `tmux` → enable
5. `stdout` is a TTY → enable
6. Otherwise → disable (no escape codes emitted at all)

When color is disabled, all output is plain text with no formatting. The editor remains fully functional.

The terminal type is forced to `xterm-256color` at startup via `os.environ.setdefault('TERM', 'xterm-256color')` if not already set.

---

## Architecture Overview

vs-cli is structured as five cooperating classes plus a collection of module-level utility functions.

```
VsCli  (main application loop)
├── Terminal          (blessed — terminal I/O, size, key input)
├── FileTree          (directory tree, expand/collapse, navigation)
├── EditorState       (buffer, cursor, undo/redo, all editing operations)
├── SmartBar          (floating modal input, seven modes)
└── TermPanel         (integrated terminal, subprocess runner)
```

Module-level functions handle syntax highlighting, git diff parsing, outline building, file icon lookup, and language detection — none of these need instance state.

### EditorState

The heart of the editor. Stores the document as a Python list of strings (`self.lines`), one string per line. Cursor is `(cy, cx)` — row and column, 0-indexed. Scroll offset is `(sy, sx)` — the top-left visible position.

**Undo stack:** A `deque(maxlen=500)` storing `(lines_copy, cy, cx)` tuples. A snapshot is taken before every destructive operation. The `_last_snap` field prevents duplicate snapshots from held keys.

Key methods:

| Method | What it does |
|---|---|
| `load(path)` | Read file, detect indent style, reset all state |
| `save()` | Write `'\n'.join(lines)` to disk |
| `insert(ch)` | Insert character with auto-close logic |
| `backspace()` | Delete with pair-deletion logic |
| `newline()` | Smart newline with auto-indent |
| `tab()` | Insert aligned spaces or a tab character |
| `move(dy, dx)` | Move cursor, clamp to buffer bounds |
| `home()` | Smart home toggle |
| `word_left()` / `word_right()` | Jump by word boundaries |
| `find_bracket_match()` | Depth-aware bracket search → `(row, col)` or `None` |
| `_snap()` | Save undo snapshot |
| `undo()` / `redo()` | Restore from snapshot stack |
| `_detect_indent()` | Scan first 200 lines to infer tab/space and width |

### FileTree

Maintains the directory tree as a flat list of item dicts, regenerated on every `refresh()`. Each item:

```python
{
  'path':     Path,
  'depth':    int,
  'is_dir':   bool,
  'expanded': bool
}
```

The set of expanded directories is tracked in `self._open` (a `set` of path strings) so it survives refreshes. Scrolling is managed by `self.scroll` (index of first visible item).

### TermPanel

Wraps `subprocess.run()` for blocking command execution. stdout + stderr are combined and appended line-by-line to a `deque(maxlen=2000)` scrollback buffer. Commands have a 30-second hard timeout.

The working directory (`self.cwd`) is updated whenever the user navigates to a new root via `Alt+W`.

### SmartBar

A state machine with seven modes. Holds the current text input, a results list, and a selected index. The `update()` method recomputes results on every keystroke using the appropriate strategy for the current mode.

Replace mode is special: it carries two text fields (`text` for find, `replace_text` for replace) and a `replace_field` integer toggle (0 or 1).

### VsCli (Main)

Owns all other components. Its main loop:

```python
while running:
    _sync()    # reconcile scroll positions
    render()   # draw the entire screen
    key = t.inkey(timeout=0.05)
    if key:
        msg_err = False
        msg = ''
        handle(key)
```

`handle()` dispatches to the appropriate subsystem based on focus state and key identity. Global shortcuts are checked first before focus-specific dispatch.

---

## Rendering Engine

The renderer uses absolute cursor positioning (`t.move(row, col)`) to write every visible cell, top to bottom, left to right. The entire visible screen is unconditionally redrawn every frame — there is no diffing.

**Why full redraws?** At 20fps (50ms poll timeout), redrawing a typical 80×40 terminal takes well under 2ms of string work. The simplicity of unconditional redraws outweighs the marginal performance gain of a diff renderer, which would require significantly more code and state.

**Flicker prevention:** All output for a single frame is accumulated into a Python list, joined with `''.join()`, and emitted in a single `sys.stdout.write()` call. From the terminal emulator's perspective this write is atomic, preventing partial-draw flicker.

**Layer order** (later items paint over earlier ones):

1. Title bar
2. Sidebar / file tree
3. Git gutter
4. Divider
5. Line numbers
6. Editor content (syntax highlighted)
7. Sticky scroll pin (if active and viewport scrolled)
8. Cursor block
9. Bracket match highlight
10. Terminal panel (if open)
11. Status bar
12. SmartBar floating box (if active — always topmost)

---

## Known Limitations

- **No PTY in terminal panel.** Interactive programs (`vim`, `htop`, `less`, `ssh`, Python REPL) will not work correctly. The terminal is for non-interactive commands only.
- **Branch name is static.** The status bar always shows `⎇ main`. It does not query git for the actual branch name.
- **No multi-file editing / tabs.** Only one buffer is open at a time. Quick-open replaces the current buffer.
- **No selection, cut, copy, or paste.** There is no visual selection mode. Your terminal emulator's native mouse selection still works for copying text out of the editor.
- **No syntax highlighting for most languages.** Only Python, JavaScript/TypeScript, JSON, and Markdown have highlighters. All others render as plain text.
- **Highlighting is not a real parser.** The tokenizer is regex and state-machine based. Multiline strings, complex escape sequences, and edge cases in real code may be colored incorrectly.
- **Undo history is not persistent.** Closing and reopening a file resets the undo stack.
- **No word wrap.** Long lines are horizontally scrollable but not wrapped.
- **No regex search or replace.** All searches (in-file, grep, replace) are plain string matching.
- **Replace is case-sensitive only.** There is no case-insensitive replace option.
- **Outline view supports Python and JS/TS only.** Other languages show an empty outline.
- **Terminal timeout is 30 seconds.** Long-running commands are killed. There is no way to cancel a running command mid-execution or send input to it.
- **No save-as dialog.** Saving always writes to the current `filepath`. Changing the filename requires editing the buffer's `filepath` attribute in code.

---

## Configuration & Customization

There is no configuration file. All defaults are hardcoded as class-level constants and module-level dicts. To change them, edit the source.

**Key constants:**

```python
# VsCli class — layout dimensions
SW     = 26   # sidebar width in columns
LW     = 5    # line number gutter width in columns
GW     = 1    # git gutter width in columns
TERM_H = 12   # terminal panel height in rows

# Module level — undo stack size
_UNDO_LIMIT = 500

# Module level — directories hidden from file tree
_SKIP = frozenset((
    '.git', '__pycache__', 'node_modules', 'venv', ...
))
```

**To add a new language for syntax highlighting:**

1. Add the extension(s) to `_EXT_LANG`
2. Write a `_hl_yourlang(line: str) -> str` function
3. Add a branch for it in the `highlight()` dispatcher

**To add a new command to the command palette:**

1. Add a `('command_name', 'description')` tuple to `_CMDS`
2. Handle the command string in `VsCli._exec()`

**To add a new file icon:**

Add an entry to `_EXT_ICON` — keys are lowercase extensions with the leading dot (e.g., `'.kt'`), values are 3-character strings.

---

## FAQ

**Q: Why `blessed` and not `curses`?**

`blessed` is a thin, well-maintained wrapper around curses providing a cleaner API for terminal size, key input, and ANSI codes. It handles platform differences more gracefully than raw curses. The package is tiny (~50KB installed) with no transitive dependencies.

**Q: Does this work on Windows?**

Possibly, with Windows Terminal or WSL. Native cmd.exe / PowerShell have limited ANSI support and may not render correctly. This is not tested or officially supported.

**Q: Does this work over SSH?**

Yes — this is one of the primary use cases. You need Python 3.10+ and `blessed` installed on the remote machine.

**Q: Can I open multiple files at once?**

Not currently. Only one buffer exists at a time. Use the file explorer (`F5`) or Quick Open (`Ctrl+P`) to switch files.

**Q: Why does the terminal panel kill my process after 30 seconds?**

The terminal uses blocking `subprocess.run()` with a fixed timeout to keep the implementation simple and avoid zombie processes. If you need to run a long command, use a separate terminal window.

**Q: How do I create a new file?**

Run the `new` command from the command palette (`Shift+F6` → type `new` → `Enter`). This opens an untitled Python buffer. Save it with `Ctrl+S`.

**Q: The colors look wrong / garbled.**

Make sure your terminal advertises 256-color support. Set `TERM=xterm-256color` before running if needed. Set `NO_COLOR=1` to disable all color output and get plain text.

**Q: Why does `Home` not go to column 0?**

`Home` is a smart toggle: first press goes to the first non-whitespace character, second press goes to column 0. This matches the behavior in VS Code, JetBrains IDEs, and many other editors. If you are already at the indent position, it goes to column 0. Press it again to return.

**Q: What does the `*` in the title bar mean?**

The asterisk after the filename indicates unsaved changes. It disappears when you save with `Ctrl+S`.

---

## Contributing

The codebase is intentionally a single file with minimal abstractions. Before contributing, please consider whether your change can be done without:

- Adding new dependencies
- Introducing a config file system
- Splitting into multiple files
- Adding more than ~50 lines of code

Good candidates for contribution:

- Additional syntax highlighters (keeping the hand-rolled per-line approach)
- Dynamic branch name detection via `git branch --show-current`
- Save-as dialog (a new SmartBar mode with a path input)
- Case-insensitive search toggle
- Line count and file size in the status bar
- Configurable key bindings via environment variables or a dotfile

# WARNING vs-cli is a BlueArch Project!

**The single-file constraint is intentional and non-negotiable.** The entire value proposition of vs-cli is that you can `curl` one file onto a server and have a working editor. Please respect this.

---

## License

MIT. Do what you want. Attribution appreciated but not required.

---

*vs-cli — because sometimes you just need an editor that works.*

