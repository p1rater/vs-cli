#!/usr/bin/env python3
"""
vs-cli  —  a tiny terminal IDE that somehow works
built on top of blessed, which does all the hard terminal stuff for us
"""

import os
import sys
import re
import subprocess
import shlex
from pathlib import Path
from collections import deque

# blessed needs TERM to be set or it refuses to do colors
os.environ.setdefault('TERM', 'xterm-256color')

from blessed import Terminal

# ---------------------------------------------------------------------------
# colors
# these are just ANSI 256-color escape strings. works on pretty much every
# modern terminal. if yours shows garbage, set NO_COLOR=1 to disable.
# ---------------------------------------------------------------------------

def _esc(code):
    return f'\x1b[{code}m'

def _has_color():
    if os.environ.get('NO_COLOR'):
        return False
    t = os.environ.get('TERM', '')
    c = os.environ.get('COLORTERM', '')
    return (c in ('truecolor', '24bit', 'yes')
            or '256color' in t or 'color' in t
            or t in ('xterm', 'screen', 'tmux')
            or sys.stdout.isatty())

_C = _has_color()

def fg(n):  return _esc(f'38;5;{n}') if _C else ''
def bg(n):  return _esc(f'48;5;{n}') if _C else ''
def R():    return _esc('0') if _C else ''
def B():    return _esc('1') if _C else ''

# pre-bake so we're not calling R() a million times per render
_R = R(); _B = B()

# color palette
KW   = fg(39)   # keywords      blue-ish
STR  = fg(214)  # strings       orange
NUM  = fg(150)  # numbers       soft green
CMT  = fg(242)  # comments      gray, as god intended
FN   = fg(221)  # function names yellow
TYP  = fg(78)   # types/classes teal
HHH  = fg(39)   # md headings
BUL  = fg(78)   # md bullets
TBL  = fg(242)  # md tables

# ---------------------------------------------------------------------------
# syntax highlighting
# this is basically a hand-rolled tokenizer. it's not perfect and will
# absolutely choke on weird edge cases, but it's good enough for showing
# colors without pulling in a full parser.
# ---------------------------------------------------------------------------

_JS_KW = {
    'const','let','var','function','class','import','export','from',
    'return','if','else','for','while','async','await','new','this',
    'typeof','instanceof','try','catch','throw','default','switch',
    'case','break','continue','null','true','false','undefined','of','in',
}

_PY_KW = {
    'def','class','import','from','return','if','elif','else','for',
    'while','and','or','not','in','is','True','False','None','try',
    'except','finally','raise','with','as','lambda','pass','break',
    'continue','global','nonlocal','yield','async','await',
}


def _hl_code(line, kws):
    """tokenize a line of JS/Python and paint the pieces"""
    out = []
    i, n = 0, len(line)
    s = line.lstrip()

    # full-line comment  (#  or  //)
    if s.startswith('#') or s.startswith('//'):
        return line[:n - len(s)] + CMT + s + _R

    in_str = None
    buf = ''

    while i < n:
        ch = line[i]

        if in_str:
            buf += ch
            if ch == '\\' and i + 1 < n:
                buf += line[i+1]; i += 2; continue
            if ch == in_str:
                out.append(STR + buf + _R); buf = ''; in_str = None
            i += 1; continue

        if ch == '/' and i+1 < n and line[i+1] == '/':
            out.append(CMT + line[i:] + _R); break

        if ch in ('"', "'", '`'):
            in_str = ch; buf = ch; i += 1; continue

        if ch.isalpha() or ch == '_':
            j = i
            while j < n and (line[j].isalnum() or line[j] == '_'):
                j += 1
            word = line[i:j]
            rest = line[j:].lstrip()
            if word in kws:
                out.append(KW + word + _R)
            elif word and word[0].isupper():
                out.append(TYP + word + _R)
            elif rest.startswith('('):
                out.append(FN + word + _R)
            else:
                out.append(word)
            i = j; continue

        if ch.isdigit():
            j = i
            while j < n and (line[j].isdigit() or line[j] in '.eE+-_'):
                j += 1
            out.append(NUM + line[i:j] + _R); i = j; continue

        out.append(ch); i += 1

    if buf:
        out.append(STR + buf + _R)
    return ''.join(out)


def _hl_json(line):
    out = []
    j = 0
    n = len(line)
    while j < n and line[j] in ' \t':
        j += 1
    out.append(line[:j])
    rest = line[j:]
    m = re.match(r'^("(?:[^"\\]|\\.)*")\s*(:)', rest)
    if m:
        out.append(KW + m.group(1) + _R + m.group(2))
        val = rest[m.end():]
        vs = val.strip()
        if vs.startswith('"'):
            out.append(STR + val + _R)
        elif re.match(r'^\s*-?\d', val) or vs.rstrip(',') in ('true','false','null'):
            out.append(NUM + val + _R)
        else:
            out.append(val)
        return ''.join(out)
    vs = rest.strip()
    if vs.startswith('"'):
        out.append(STR + rest + _R)
    elif re.match(r'^-?\d', vs) or vs.rstrip(',') in ('true','false','null'):
        out.append(NUM + rest + _R)
    else:
        out.append(rest)
    return ''.join(out)


def _hl_md(line):
    if re.match(r'^#{1,6} ', line):
        return _B + HHH + line + _R
    if re.match(r'^\s*[-*+] ', line):
        return BUL + line + _R
    if re.match(r'^\|', line):
        return TBL + line + _R
    # inline code and bold — close enough
    out = re.sub(r'`([^`]+)`', lambda m: STR + '`' + m.group(1) + '`' + _R, line)
    out = re.sub(r'\*\*([^*]+)\*\*', lambda m: _B + m.group(1) + _R, out)
    return out


def highlight(line, lang):
    # wrap in try/except so a bad line never crashes the render loop
    try:
        if lang in ('js', 'ts'):  return _hl_code(line, _JS_KW)
        if lang == 'py':          return _hl_code(line, _PY_KW)
        if lang == 'json':        return _hl_json(line)
        if lang == 'md':          return _hl_md(line)
    except Exception:
        pass
    return line


# ---------------------------------------------------------------------------
# utils
# ---------------------------------------------------------------------------

def get_lang(filename):
    ext = Path(filename).suffix.lower().lstrip('.')
    return {
        'js':'js','ts':'js','jsx':'js','tsx':'js',
        'py':'py','json':'json','md':'md','sh':'sh',
        'css':'css','html':'html',
    }.get(ext, 'text')


def file_icon(name, is_dir, expanded=False):
    if is_dir:
        return '▾ ' if expanded else '▸ '
    return {
        '.js':'JS ','.ts':'TS ','.py':'PY ','.json':'{} ',
        '.md':'MD ','.css':'CS ','.html':'HT ','.sh':'SH ',
        '.txt':'TX ','.yml':'YM ','.yaml':'YM ','.env':'EN ',
        '.rs':'RS ','.go':'GO ','.rb':'RB ','.cpp':'C+ ',
    }.get(Path(name).suffix.lower(), '   ')


# ---------------------------------------------------------------------------
# editor state
# just a list of strings + cursor position. nothing fancy.
# ---------------------------------------------------------------------------

class EditorState:
    def __init__(self):
        self.lines     = ['']
        self.cx = self.cy = 0   # cursor col, row
        self.sx = self.sy = 0   # scroll col, row
        self.filepath  = None
        self.modified  = False
        self.lang      = 'text'

    def load(self, path):
        self.filepath = path
        self.lang = get_lang(path)
        try:
            text = Path(path).read_text(errors='replace')
            self.lines = text.split('\n') or ['']
        except OSError:
            self.lines = ['']
        self.cx = self.cy = self.sx = self.sy = 0
        self.modified = False

    def save(self):
        if not self.filepath:
            return False
        try:
            Path(self.filepath).write_text('\n'.join(self.lines))
            self.modified = False
            return True
        except OSError:
            return False

    def insert(self, ch):
        line = self.lines[self.cy]
        self.lines[self.cy] = line[:self.cx] + ch + line[self.cx:]
        self.cx += 1
        self.modified = True

    def backspace(self):
        if self.cx > 0:
            line = self.lines[self.cy]
            self.lines[self.cy] = line[:self.cx-1] + line[self.cx:]
            self.cx -= 1
            self.modified = True
        elif self.cy > 0:
            prev = self.lines[self.cy - 1]
            self.cx = len(prev)
            self.lines[self.cy-1] = prev + self.lines[self.cy]
            self.lines.pop(self.cy)
            self.cy -= 1
            self.modified = True

    def delete_fwd(self):
        line = self.lines[self.cy]
        if self.cx < len(line):
            self.lines[self.cy] = line[:self.cx] + line[self.cx+1:]
            self.modified = True
        elif self.cy < len(self.lines) - 1:
            self.lines[self.cy] += self.lines[self.cy+1]
            self.lines.pop(self.cy+1)
            self.modified = True

    def newline(self):
        line = self.lines[self.cy]
        indent = len(line) - len(line.lstrip())
        self.lines[self.cy] = line[:self.cx]
        self.lines.insert(self.cy+1, ' '*indent + line[self.cx:])
        self.cy += 1
        self.cx = indent
        self.modified = True

    def move(self, dy, dx):
        self.cy = max(0, min(len(self.lines)-1, self.cy + dy))
        if dx:
            self.cx = max(0, min(len(self.lines[self.cy]), self.cx + dx))
        else:
            self.cx = min(self.cx, len(self.lines[self.cy]))

    def page(self, rows, d):
        self.cy = max(0, min(len(self.lines)-1, self.cy + d*rows))
        self.cx = min(self.cx, len(self.lines[self.cy]))

    def home(self):
        indent = len(self.lines[self.cy]) - len(self.lines[self.cy].lstrip())
        self.cx = 0 if self.cx != indent else 0

    def end(self):
        self.cx = len(self.lines[self.cy])


# ---------------------------------------------------------------------------
# file tree
# walks the real filesystem. ignores the usual garbage dirs.
# ---------------------------------------------------------------------------

class FileTree:
    _SKIP = {'.git','__pycache__','.DS_Store','node_modules',
             '.pytest_cache','.mypy_cache','venv','.venv','.tox'}

    def __init__(self, root):
        self.root     = root
        self.items    = []
        self.selected = 0
        self.scroll   = 0
        self._open    = set()  # set of str paths that are expanded
        self.refresh()

    def refresh(self):
        self.items = []
        self._walk(self.root, 0)

    def _walk(self, path, depth):
        try:
            entries = sorted(path.iterdir(),
                             key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return
        for e in entries:
            if e.name in self._SKIP or e.name.startswith('.'):
                continue
            node = {'path': e, 'depth': depth, 'is_dir': e.is_dir(),
                    'expanded': str(e) in self._open}
            self.items.append(node)
            if node['is_dir'] and node['expanded']:
                self._walk(e, depth+1)

    def toggle(self):
        if not self.items:
            return
        n = self.items[self.selected]
        if n['is_dir']:
            key = str(n['path'])
            if key in self._open:
                self._open.discard(key)
            else:
                self._open.add(key)
            self.refresh()

    def go_up(self):
        if self.root.parent != self.root:
            self.root = self.root.parent
            self.selected = self.scroll = 0
            self.refresh()

    def current(self):
        return self.items[self.selected] if self.items else None

    def move(self, d):
        self.selected = max(0, min(len(self.items)-1, self.selected + d))


# ---------------------------------------------------------------------------
# terminal panel
# runs subprocesses and captures output into a scrollback buffer.
# F9+A to open, F9+C to close. blocking, not a real pty, but works fine
# for quick commands like git, ls, python scripts, etc.
# ---------------------------------------------------------------------------

class TermPanel:
    MAX_LINES = 500  # don't buffer forever

    def __init__(self, cwd):
        self.cwd    = cwd
        self.output = deque(maxlen=self.MAX_LINES)
        self.input  = ''
        self.scroll = 0
        self.active = False
        self.output.append(f'  terminal  —  {cwd}')
        self.output.append('  type a command and press Enter')
        self.output.append('')

    def run_cmd(self, cmd):
        if not cmd.strip():
            return
        self.output.append(f'$ {cmd}')
        try:
            result = subprocess.run(
                shlex.split(cmd),
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                timeout=15,
                errors='replace',
            )
            for line in (result.stdout + result.stderr).splitlines():
                self.output.append('  ' + line)
            if result.returncode != 0:
                self.output.append(f'  [exit {result.returncode}]')
        except FileNotFoundError:
            self.output.append(f'  command not found: {cmd.split()[0]}')
        except subprocess.TimeoutExpired:
            self.output.append('  timed out after 15s')
        except Exception as e:
            self.output.append(f'  error: {e}')
        self.output.append('')
        # auto-scroll to bottom after each command
        self.scroll = max(0, len(self.output) - 1)

    def type_char(self, ch): self.input += ch
    def backspace(self):     self.input = self.input[:-1]
    def scroll_up(self, n=3):   self.scroll = max(0, self.scroll - n)
    def scroll_down(self, n=3): self.scroll = min(max(0, len(self.output)-1), self.scroll + n)


# ---------------------------------------------------------------------------
# smart bar  (search / path nav / command palette)
# pops up a little floating box. Esc closes it.
# ---------------------------------------------------------------------------

COMMANDS = [
    ('save',       'save current file'),
    ('new',        'new empty buffer'),
    ('help',       'show keybindings'),
    ('git status', 'git status --short'),
    ('git log',    'last 10 commits'),
    ('exit',       'quit vs-cli'),
]


class SmartBar:
    SEARCH = 'search'
    PATH   = 'path'
    CMD    = 'cmd'

    def __init__(self):
        self.active  = None
        self.text    = ''
        self.results = []
        self.idx     = 0

    def open(self, mode):
        self.active = mode; self.text = ''; self.results = []; self.idx = 0

    def close(self):
        self.active = None; self.text = ''; self.results = []

    def is_open(self): return self.active is not None

    def type_char(self, ch): self.text += ch
    def backspace(self):     self.text = self.text[:-1]

    def nav(self, d):
        if self.results:
            self.idx = (self.idx + d) % len(self.results)

    def update(self, editor):
        if self.active == self.SEARCH:
            q = self.text.lower()
            self.results = []
            if q:
                for i, line in enumerate(editor.lines):
                    if q in line.lower():
                        self.results.append(f'{i+1:5d}  {line.rstrip()[:56]}')
        elif self.active == self.CMD:
            q = self.text.lower()
            self.results = [
                f'{cmd:<16} {desc}' for cmd, desc in COMMANDS
                if not q or q in cmd
            ]

    def search_line(self):
        if self.active == self.SEARCH and self.results:
            try:
                return int(self.results[self.idx].strip().split()[0]) - 1
            except (IndexError, ValueError):
                return None

    def selected_cmd(self):
        if self.active == self.CMD and self.results:
            return self.results[self.idx].split()[0]
        return self.text.strip()


# ---------------------------------------------------------------------------
# help screen
# ---------------------------------------------------------------------------

HELP_TEXT = """
  vs-cli  —  keybindings

  F5              focus file explorer
  F6              focus editor
  Shift+F6        command palette
  F9 then A       open terminal panel
  F9 then C       close terminal panel

  Alt+S           search in file
  Alt+W           go to folder path

  Ctrl+S          save file
  Ctrl+Q          quit

  in explorer:
    ↑↓            navigate
    Enter         open file / toggle folder
    Backspace     go to parent dir

  in editor:
    arrows        move cursor
    PgUp/PgDn     scroll fast
    Home/End      line start / end

  in terminal:
    type + Enter  run command
    ↑↓            scroll output
    Esc           back to editor

  press any key to close this
""".strip().split('\n')


# ---------------------------------------------------------------------------
# the app itself
# render() builds a big list of strings and blasts them to stdout in one
# write — avoids flicker better than doing lots of small individual writes.
# ---------------------------------------------------------------------------

class VsCli:
    SW     = 26   # sidebar width
    LW     = 5    # line number gutter width
    TERM_H = 12   # height of terminal panel

    def __init__(self, root):
        self.t         = Terminal()
        self.tree      = FileTree(root)
        self.editor    = EditorState()
        self.bar       = SmartBar()
        self.term_pan  = TermPanel(root)
        self.focus     = 'editor'   # 'explorer' | 'editor' | 'terminal'
        self.message   = ''
        self.msg_err   = False
        self.show_help = False
        self.running   = True
        self._f9       = False   # True when we got F9 and are waiting for the second key

    def EH(self):
        # editor height shrinks when terminal panel is open
        base = self.t.height - 2
        if self.term_pan.active:
            base -= self.TERM_H + 1
        return max(4, base)

    def EW(self):
        return max(10, self.t.width - self.SW - self.LW - 2)

    # render ----------------------------------------------------------------

    def render(self):
        t  = self.t
        W  = t.width
        EH = self.EH()
        EW = self.EW()
        es = self.SW + 1 + self.LW   # editor start column
        ed = self.editor
        out = [t.home]

        # title bar
        name  = Path(ed.filepath).name if ed.filepath else ''
        dirty = '*' if ed.modified else ''
        title = f' vs-cli  {"—  " + name + dirty if name else ""}'
        out.append(bg(234) + fg(245) + _B + title.ljust(W)[:W] + _R)

        # sidebar header
        exp_hl = self.focus == 'explorer'
        out.append(t.move(1, 0) +
                   (bg(235) + fg(252) + _B if exp_hl else bg(233) + fg(244)) +
                   ' EXPLORER'.ljust(self.SW)[:self.SW] + _R)

        # file tree items
        for i in range(EH - 1):
            row = i + 2
            idx = self.tree.scroll + i
            if idx >= len(self.tree.items):
                out.append(t.move(row, 0) + bg(233) + ' '*self.SW + _R)
                continue
            n   = self.tree.items[idx]
            sel = (idx == self.tree.selected and exp_hl)
            ind = '  ' * n['depth']
            ico = file_icon(n['path'].name, n['is_dir'], n['expanded'])
            lbl = (ind + ico + n['path'].name)[:self.SW-1].ljust(self.SW)
            if sel:           sty = bg(32) + fg(255)
            elif n['is_dir']: sty = bg(233) + fg(250)
            else:             sty = bg(233) + fg(244)
            out.append(t.move(row, 0) + sty + lbl + _R)

        # vertical divider between sidebar and editor
        for r in range(1, t.height - 1):
            out.append(t.move(r, self.SW) + bg(236) + fg(238) + '│' + _R)

        # line number gutter
        for i in range(EH):
            ln  = ed.sy + i + 1
            row = i + 1
            if ln <= len(ed.lines):
                cur = (ed.sy + i == ed.cy)
                sty = bg(235) + _B + fg(244) if cur else bg(234) + fg(238)
                out.append(t.move(row, self.SW+1) + sty + f'{ln:>{self.LW-1}} ' + _R)
            else:
                out.append(t.move(row, self.SW+1) + bg(234) + ' '*self.LW + _R)

        # editor content (or help screen)
        if self.show_help:
            for i in range(EH):
                txt = HELP_TEXT[i] if i < len(HELP_TEXT) else ''
                out.append(t.move(i+1, es) + bg(235) + fg(252) + txt[:EW].ljust(EW) + _R)
        else:
            for i in range(EH):
                li  = ed.sy + i
                cur = (li == ed.cy)
                lbg = bg(235) if cur else bg(234)
                if li < len(ed.lines):
                    raw = ed.lines[li]
                    vis = raw[ed.sx : ed.sx + EW]
                    hl  = highlight(vis, ed.lang)
                    pad = max(0, EW - len(vis))
                    out.append(t.move(i+1, es) + lbg + hl + lbg + ' '*pad + _R)
                else:
                    out.append(t.move(i+1, es) + bg(234) + ' '*EW + _R)

        # cursor block (only in editor focus, not help/bar)
        if self.focus == 'editor' and not self.show_help and not self.bar.is_open():
            sr = ed.cy - ed.sy + 1
            sc = ed.cx - ed.sx + es
            if 1 <= sr <= EH and es <= sc < es + EW:
                ch = (ed.lines[ed.cy][ed.cx:ed.cx+1]
                      if ed.cy < len(ed.lines) else ' ') or ' '
                out.append(t.move(sr, sc) + bg(7) + fg(0) + ch + _R)

        # terminal panel (if open)
        if self.term_pan.active:
            self._render_terminal(out, EH, EW, es, W)

        # status bar
        fbg  = 26 if self.focus in ('editor', 'terminal') else 22
        lang = ed.lang.upper() if ed.filepath else '  '
        pos  = f'Ln {ed.cy+1}, Col {ed.cx+1}'
        mode = {'editor':'INSERT', 'explorer':'EXPLORE', 'terminal':'TERMINAL'}.get(self.focus, '')
        mc   = fg(203) if self.msg_err else fg(252)
        left  = f'  {mode}  ⎇ main  {self.message[:50]}'
        right = f' {pos}  {lang}  UTF-8  '
        mid   = max(0, W - len(left) - len(right))
        sb    = bg(fbg) + _B + fg(255) + left + mc + ' '*mid + fg(230) + right + _R
        out.append(t.move(t.height-1, 0) + sb[:W].ljust(W)[:W])

        # smart bar floats on top of everything else
        if self.bar.is_open():
            out += self._render_bar()

        sys.stdout.write(''.join(out))
        sys.stdout.flush()

    def _render_terminal(self, out, EH, EW, es, W):
        t   = self.t
        TH  = self.TERM_H
        TW  = W - self.SW - 2
        top = EH + 2   # first row of terminal (after editor rows + title row)

        # separator
        tit = ' TERMINAL '
        sep = ('╌' * ((TW - len(tit)) // 2) + tit +
               '╌' * ((TW - len(tit) + 1) // 2))[:TW]
        tfg = fg(39) if self.focus == 'terminal' else fg(238)
        out.append(t.move(top-1, self.SW+1) + bg(232) + tfg + sep + _R)

        # output scrollback
        lines = list(self.term_pan.output)
        start = max(0, self.term_pan.scroll - TH + 2)
        vis   = lines[start : start + TH - 1]
        for i in range(TH - 1):
            row = top + i
            txt = vis[i] if i < len(vis) else ''
            out.append(t.move(row, self.SW+1) + bg(232) + fg(245) + txt[:TW].ljust(TW) + _R)

        # input line at the bottom of the panel
        prompt = f' $ {self.term_pan.input}_'
        isty   = (bg(235) + fg(255) if self.focus == 'terminal'
                  else bg(232) + fg(240))
        out.append(t.move(top + TH - 1, self.SW+1) + isty + prompt[:TW].ljust(TW) + _R)

    def _render_bar(self):
        t, W, H, b = self.t, self.t.width, self.t.height, self.bar
        out = []
        if b.active == SmartBar.SEARCH:
            bw, bx, by = W - self.SW - 4, self.SW + 2, 1
            title = ' SEARCH IN FILE '
        elif b.active == SmartBar.PATH:
            bw = min(62, W-4); bx = max(0, W//2-bw//2); by = H//2-3
            title = ' GO TO FOLDER '
        else:
            bw = min(56, W-4); bx = max(0, W//2-bw//2); by = H//2-4
            title = ' COMMAND PALETTE '

        inner = bw - 2
        top   = '╭' + title.center(inner, '─') + '╮'
        sep   = '├' + '─'*inner + '┤'
        bot   = '╰' + '─'*inner + '╯'
        prompt = f'  {b.text}_'
        out.append(t.move(by,   bx) + bg(236) + _B + fg(39)  + top[:bw] + _R)
        out.append(t.move(by+1, bx) + bg(236) + fg(255) + '│' + prompt[:inner].ljust(inner) + '│' + _R)
        out.append(t.move(by+2, bx) + bg(236) + fg(238) + sep[:bw] + _R)
        results = b.results[:6]
        for i, res in enumerate(results):
            sty = bg(32)+fg(255) if i == b.idx else bg(236)+fg(245)
            out.append(t.move(by+3+i, bx) + sty + '│ ' + res[:inner-4].ljust(inner-4) + ' │' + _R)
        for i in range(len(results), 4):
            out.append(t.move(by+3+i, bx) + bg(236) + '│' + ' '*inner + '│' + _R)
        hints = {
            SmartBar.SEARCH: '  ↑↓ navigate · Enter jump · Esc close',
            SmartBar.PATH:   '  Enter go · Esc close',
            SmartBar.CMD:    '  Enter run · ↑↓ select · Esc close',
        }
        end = by + 3 + max(len(results), 4)
        out.append(t.move(end,   bx) + bg(236)+fg(238) + '│' + hints.get(b.active,'')[:inner].ljust(inner) + '│' + _R)
        out.append(t.move(end+1, bx) + bg(236)+fg(39)  + bot[:bw] + _R)
        return out

    # scroll sync — call before render() ------------------------------------

    def _sync(self):
        ed, EH, EW = self.editor, self.EH(), self.EW()
        if ed.cy < ed.sy:              ed.sy = ed.cy
        elif ed.cy >= ed.sy + EH:      ed.sy = ed.cy - EH + 1
        if ed.cx < ed.sx:              ed.sx = ed.cx
        elif ed.cx >= ed.sx + EW:      ed.sx = ed.cx - EW + 1
        vis = EH - 1
        if self.tree.selected < self.tree.scroll:
            self.tree.scroll = self.tree.selected
        elif self.tree.selected >= self.tree.scroll + vis:
            self.tree.scroll = self.tree.selected - vis + 1

    # input -----------------------------------------------------------------

    def handle(self, key):
        if self.show_help:
            self.show_help = False
            return

        raw = str(key)

        # F9 chord — F9 sets the flag, next keypress decides what to do
        if key.name == 'KEY_F9':
            self._f9 = True
            return

        if self._f9:
            self._f9 = False
            if raw.lower() == 'a':
                self.term_pan.active = True
                self.focus = 'terminal'
                self.message = 'terminal open  —  F9 then C to close'
                return
            if raw.lower() == 'c':
                self.term_pan.active = False
                if self.focus == 'terminal':
                    self.focus = 'editor'
                self.message = 'terminal closed'
                return
            # not a chord we recognise, fall through

        # terminal panel handles its own keys when focused
        if self.focus == 'terminal':
            if   key.name == 'KEY_ESCAPE':    self.focus = 'editor'
            elif key.name == 'KEY_ENTER':
                self.term_pan.run_cmd(self.term_pan.input)
                self.term_pan.input = ''
            elif key.name == 'KEY_BACKSPACE': self.term_pan.backspace()
            elif key.name == 'KEY_UP':        self.term_pan.scroll_up()
            elif key.name == 'KEY_DOWN':      self.term_pan.scroll_down()
            elif not key.is_sequence and key: self.term_pan.type_char(raw)
            return

        # smart bar steals all input when it's open
        if self.bar.is_open():
            if   key.name == 'KEY_ESCAPE':    self.bar.close()
            elif key.name == 'KEY_ENTER':     self._bar_confirm()
            elif key.name == 'KEY_UP':        self.bar.nav(-1)
            elif key.name == 'KEY_DOWN':      self.bar.nav(1)
            elif key.name == 'KEY_BACKSPACE': self.bar.backspace(); self.bar.update(self.editor)
            elif not key.is_sequence and key: self.bar.type_char(raw); self.bar.update(self.editor)
            return

        # global shortcuts
        if key.name == 'KEY_F5':
            self.focus = 'explorer'
            self.message = 'explorer — arrows+Enter, Backspace=parent dir'
            return
        if raw in ('\x1b[17;2~', '\x1b[1;2Q'):   # Shift+F6
            self.bar.open(SmartBar.CMD); self.bar.update(self.editor); return
        if key.name == 'KEY_F6':
            self.focus = 'editor'; self.message = ''; return
        if raw in ('\x1bs', '\x1bS'):             # Alt+S
            self.bar.open(SmartBar.SEARCH); self.bar.update(self.editor); return
        if raw in ('\x1bw', '\x1bW'):             # Alt+W
            self.bar.open(SmartBar.PATH); self.bar.text = str(self.tree.root); return
        if raw == '\x13':                         # Ctrl+S
            self.message = (f'saved  {Path(self.editor.filepath).name}'
                            if self.editor.save() else 'nothing to save')
            return
        if raw == '\x11':                         # Ctrl+Q
            self.running = False; return

        # explorer navigation
        if self.focus == 'explorer':
            if   key.name == 'KEY_DOWN':  self.tree.move(1)
            elif key.name == 'KEY_UP':    self.tree.move(-1)
            elif key.name == 'KEY_ENTER':
                n = self.tree.current()
                if n:
                    if n['is_dir']:   self.tree.toggle()
                    else:
                        self.editor.load(str(n['path']))
                        self.message = f'opened  {n["path"].name}'
                        self.focus = 'editor'
            elif key.name == 'KEY_BACKSPACE':
                self.tree.go_up()
                self.message = f'↑  {self.tree.root}'
            return

        # editor — plain text editing
        if self.focus == 'editor':
            ed = self.editor
            if   key.name == 'KEY_UP':        ed.move(-1, 0)
            elif key.name == 'KEY_DOWN':      ed.move( 1, 0)
            elif key.name == 'KEY_LEFT':      ed.move( 0,-1)
            elif key.name == 'KEY_RIGHT':     ed.move( 0, 1)
            elif key.name == 'KEY_HOME':      ed.home()
            elif key.name == 'KEY_END':       ed.end()
            elif key.name == 'KEY_PGUP':      ed.page(self.EH()-2, -1)
            elif key.name == 'KEY_PGDOWN':    ed.page(self.EH()-2,  1)
            elif key.name == 'KEY_ENTER':     ed.newline()
            elif key.name == 'KEY_BACKSPACE': ed.backspace()
            elif key.name == 'KEY_DELETE':    ed.delete_fwd()
            elif raw == '\t':                 [ed.insert(' ') for _ in range(2)]
            elif not key.is_sequence and key: ed.insert(raw)

    def _bar_confirm(self):
        b = self.bar
        if b.active == SmartBar.SEARCH:
            ln = b.search_line()
            if ln is not None:
                self.editor.cy = ln; self.editor.cx = 0
                self.message = f'jumped to line {ln+1}'
            b.close(); self.focus = 'editor'

        elif b.active == SmartBar.PATH:
            p = Path(b.text.strip()).expanduser()
            if p.is_dir():
                self.tree.root = p
                self.tree.selected = self.tree.scroll = 0
                self.tree._open.clear(); self.tree.refresh()
                self.term_pan.cwd = p
                self.message = f'→  {p}'; self.focus = 'explorer'
            else:
                self.message = f'not found: {p}'; self.msg_err = True
            b.close()

        elif b.active == SmartBar.CMD:
            cmd = b.selected_cmd(); b.close(); self._exec(cmd)

    def _exec(self, cmd):
        cmd = cmd.lower().strip()
        if cmd == 'exit':
            self.running = False
        elif cmd == 'save':
            self.message = (f'saved  {Path(self.editor.filepath).name}'
                            if self.editor.save() else 'nothing to save')
        elif cmd == 'new':
            self.editor.filepath = 'untitled.py'
            self.editor.lines    = ['']
            self.editor.cx = self.editor.cy = 0
            self.editor.modified = True; self.editor.lang = 'py'
            self.focus = 'editor'; self.message = 'new buffer'
        elif cmd == 'help':
            self.show_help = True
        elif cmd == 'git status':
            self._git('status', '--short')
        elif cmd == 'git log':
            self._git('log', '--oneline', '-10')
        else:
            self.message = f'unknown: {cmd}'; self.msg_err = True

    def _git(self, *args):
        try:
            r = subprocess.run(
                ['git', '-C', str(self.tree.root)] + list(args),
                capture_output=True, text=True, timeout=5,
            )
            self.message = (r.stdout.strip().replace('\n', '  |  ')[:60]
                            or 'working tree clean')
        except Exception:
            self.message = 'git not available'

    # main loop -------------------------------------------------------------

    def run(self):
        t = self.t
        with t.fullscreen(), t.hidden_cursor(), t.raw():
            sys.stdout.write(t.clear); sys.stdout.flush()
            # open the first file we find so the editor isn't blank on startup
            for n in self.tree.items:
                if not n['is_dir']:
                    self.editor.load(str(n['path']))
                    self.focus = 'editor'; break
            while self.running:
                self._sync()
                self.render()
                key = t.inkey(timeout=0.05)
                if key:
                    self.msg_err = False; self.message = ''
                    self.handle(key)
            sys.stdout.write(t.clear + t.home)
            sys.stdout.flush()
        print('\nvs-cli — bye!\n')


# entry point — nothing special here
def main():
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    if not root.exists():
        print(f'error: path not found: {root}'); sys.exit(1)
    app = VsCli(root.parent if root.is_file() else root)
    if root.is_file():
        app.editor.load(str(root)); app.focus = 'editor'
    app.run()


if __name__ == '__main__':
    main()
