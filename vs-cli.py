#!/usr/bin/env python3
#
# vs-cli: a terminal editor that doesn't suck (much)
#
# pip install blessed  — that's the only dependency.
#
# new in this version:
#   undo/redo (Ctrl+Z / Ctrl+Y), bracket auto-close, indentation detection,
#   global grep (Ctrl+Shift+F), quick-open (Ctrl+P), git gutter indicators,
#   outline view (Ctrl+O), zen mode (F11), sticky scroll, find+replace (Alt+R)

import os, sys, re, subprocess, shlex
from pathlib import Path
from collections import deque

os.environ.setdefault('TERM', 'xterm-256color')
from blessed import Terminal


# --- color -------------------------------------------------------------------

def _e(c):  return f'\x1b[{c}m'
def fg(n):  return _e(f'38;5;{n}') if _COL else ''
def bg(n):  return _e(f'48;5;{n}') if _COL else ''

def _detect_color():
    if os.environ.get('NO_COLOR'): return False
    t = os.environ.get('TERM', '')
    c = os.environ.get('COLORTERM', '')
    return (c in ('truecolor', '24bit') or '256color' in t
            or t in ('xterm', 'screen', 'tmux') or sys.stdout.isatty())

_COL = _detect_color()
_R   = _e('0') if _COL else ''
_B   = _e('1') if _COL else ''
_U   = _e('4') if _COL else ''   # underline, used for bracket highlight

C_KW  = fg(39);  C_STR = fg(214); C_NUM = fg(150); C_CMT = fg(242)
C_FN  = fg(221); C_TYP = fg(78);  C_HDR = fg(39);  C_BUL = fg(78)
C_BR  = fg(220)  # bracket match highlight — yellow


# --- syntax highlighting -----------------------------------------------------
#
# hand-rolled tokenizer. not a real parser, handles ~95% of real code.
# the other 5% just loses color. this is fine.

_JS_KW = frozenset((
    'break','case','catch','class','const','continue','default','delete',
    'do','else','export','extends','false','finally','for','from','function',
    'if','import','in','instanceof','let','new','null','of','return','static',
    'super','switch','this','throw','true','try','typeof','undefined','var',
    'void','while','async','await',
))
_PY_KW = frozenset((
    'False','None','True','and','as','assert','async','await','break','class',
    'continue','def','del','elif','else','except','finally','for','from',
    'global','if','import','in','is','lambda','nonlocal','not','or','pass',
    'raise','return','try','while','with','yield',
))

# pairs for bracket auto-close and matching
_PAIRS  = {'(':')', '[':']', '{':'}', '"':'"', "'":"'", '`':'`'}
_CLOSE  = set(_PAIRS.values())
_OPEN_B = frozenset('([{')
_CLOSE_B= frozenset(')]}')
_MATCH  = {')':'(', ']':'[', '}':'{', '(':')', '[':']', '{':'}'}


def _hl_code(line, kws):
    n = len(line)
    s = line.lstrip()
    if s[:1] == '#' or s[:2] == '//':
        return line[:n-len(s)] + C_CMT + s + _R

    out = []; i = 0; in_str = None; sbuf = ''
    while i < n:
        c = line[i]
        if in_str:
            sbuf += c
            if c == '\\' and i+1 < n: sbuf += line[i+1]; i += 2; continue
            if c == in_str: out.append(C_STR+sbuf+_R); sbuf=''; in_str=None
            i += 1; continue
        if c == '/' and i+1 < n and line[i+1] == '/':
            out.append(C_CMT+line[i:]+_R); break
        if c in ('"',"'",'`'): in_str=c; sbuf=c; i+=1; continue
        if c.isalpha() or c == '_':
            j = i
            while j < n and (line[j].isalnum() or line[j]=='_'): j+=1
            w = line[i:j]
            if   w in kws:                        out.append(C_KW+w+_R)
            elif w and w[0].isupper():             out.append(C_TYP+w+_R)
            elif line[j:].lstrip()[:1] == '(':    out.append(C_FN+w+_R)
            else:                                  out.append(w)
            i = j; continue
        if c.isdigit() or (c=='-' and i+1<n and line[i+1].isdigit()):
            j = i+1
            while j<n and (line[j].isdigit() or line[j] in '.eExX_abcdefABCDEF'): j+=1
            out.append(C_NUM+line[i:j]+_R); i=j; continue
        out.append(c); i+=1
    if sbuf: out.append(C_STR+sbuf+_R)
    return ''.join(out)


def _hl_json(line):
    j=0; n=len(line)
    while j<n and line[j] in ' \t': j+=1
    indent=line[:j]; rest=line[j:]
    m = re.match(r'^("(?:[^"\\]|\\.)*")\s*(:)', rest)
    if m:
        val=rest[m.end():]; vs=val.strip()
        cv = (C_STR+val+_R if vs[:1]=='"'
              else C_NUM+val+_R if re.match(r'^\s*-?\d',val) or vs.rstrip(',') in ('true','false','null')
              else val)
        return indent+C_KW+m.group(1)+_R+m.group(2)+cv
    vs=rest.strip()
    if vs[:1]=='"': return indent+C_STR+rest+_R
    if re.match(r'^-?\d',vs) or vs.rstrip(',') in ('true','false','null'): return indent+C_NUM+rest+_R
    return line


def _hl_md(line):
    if re.match(r'^#{1,6} ', line): return _B+C_HDR+line+_R
    if re.match(r'^\s*[-*+] ',line): return C_BUL+line+_R
    out = re.sub(r'`([^`]+)`',       lambda m: C_STR+'`'+m.group(1)+'`'+_R, line)
    out = re.sub(r'\*\*([^*]+)\*\*', lambda m: _B+m.group(1)+_R, out)
    return out


def highlight(line, lang):
    try:
        if lang in ('js','ts'): return _hl_code(line, _JS_KW)
        if lang == 'py':        return _hl_code(line, _PY_KW)
        if lang == 'json':      return _hl_json(line)
        if lang == 'md':        return _hl_md(line)
    except Exception: pass
    return line


# --- file utils --------------------------------------------------------------

_EXT_LANG = {
    'js':'js','ts':'js','jsx':'js','tsx':'js','mjs':'js','cjs':'js',
    'py':'py','pyi':'py','json':'json','jsonc':'json',
    'md':'md','markdown':'md','sh':'sh','bash':'sh','zsh':'sh',
    'html':'html','htm':'html','css':'css','scss':'css',
    'rs':'rs','go':'go','rb':'rb','cpp':'cpp','c':'c','h':'c',
    'toml':'toml','yaml':'yaml','yml':'yaml',
}
_EXT_ICON = {
    '.js':'JS ','.ts':'TS ','.jsx':'JS ','.tsx':'TS ','.py':'PY ',
    '.rs':'RS ','.go':'GO ','.rb':'RB ','.c':'C  ','.cpp':'C+ ','.h':'H  ',
    '.json':'{} ','.md':'MD ','.css':'CS ','.html':'HT ','.sh':'SH ',
    '.txt':'TX ','.yml':'YM ','.yaml':'YM ','.env':'EN ','.toml':'TM ','.lock':'LK ',
}

def get_lang(path): return _EXT_LANG.get(Path(path).suffix.lower().lstrip('.'), 'text')
def file_icon(name, is_dir, expanded=False):
    if is_dir: return '▾ ' if expanded else '▸ '
    return _EXT_ICON.get(Path(name).suffix.lower(), '   ')


# --- outline -----------------------------------------------------------------
#
# scans lines for function/class definitions. works for py, js, ts.
# returns list of (line_number, label) tuples.

def build_outline(lines, lang):
    out = []
    if lang in ('py',):
        pat = re.compile(r'^(\s*)(def|class)\s+(\w+)')
    elif lang in ('js','ts'):
        pat = re.compile(r'^\s*(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(|class\s+(\w+))')
    else:
        return out
    for i, line in enumerate(lines):
        m = pat.match(line)
        if m:
            indent = len(line) - len(line.lstrip())
            if lang == 'py':
                kind  = m.group(2)
                name  = m.group(3)
                prefix = '  '*(indent//4) + ('⬡ ' if kind=='class' else '⬢ ')
            else:
                name = m.group(1) or m.group(2) or m.group(3) or '?'
                prefix = '⬢ '
            out.append((i, prefix + name))
    return out


# --- git gutter --------------------------------------------------------------
#
# runs git diff to figure out which lines are added/modified/deleted.
# cached per file, refreshed on save or file open.
# returns a dict: line_number → '+' | '~' | '-'

def git_diff_markers(filepath, root):
    markers = {}
    if not filepath: return markers
    try:
        r = subprocess.run(
            ['git', '-C', str(root), 'diff', '--unified=0', '--', filepath],
            capture_output=True, text=True, timeout=3,
        )
        current_new = None
        for line in r.stdout.splitlines():
            if line.startswith('@@'):
                # @@ -old_start,old_count +new_start,new_count @@
                m = re.search(r'\+(\d+)(?:,(\d+))?', line)
                if m:
                    current_new = int(m.group(1))
                continue
            if current_new is None: continue
            if line.startswith('+'):
                markers[current_new] = '+'
                current_new += 1
            elif line.startswith('-'):
                # deletion — mark the line before as having a deletion below it
                markers[max(1, current_new-1)] = markers.get(max(1,current_new-1), '-')
            else:
                current_new += 1
    except Exception:
        pass
    return markers


# --- EditorState -------------------------------------------------------------
#
# the buffer. list of strings. cursor is (cy,cx). scroll is (sy,sx).
# undo stack stores (lines_snapshot, cy, cx) tuples. we snapshot before
# every destructive operation. bounded at 500 entries because RAM isn't free.

_UNDO_LIMIT = 500

class EditorState:
    __slots__ = ('lines','cy','cx','sy','sx','filepath','modified','lang',
                 'indent_char','indent_size',
                 '_undo','_redo','_last_snap')

    def __init__(self):
        self.lines       = ['']
        self.cy = self.cx = self.sy = self.sx = 0
        self.filepath    = None
        self.modified    = False
        self.lang        = 'text'
        self.indent_char = ' '   # ' ' or '\t'
        self.indent_size = 4     # spaces per indent level
        self._undo       = deque(maxlen=_UNDO_LIMIT)
        self._redo       = deque(maxlen=_UNDO_LIMIT)
        self._last_snap  = None  # avoid duplicate snapshots for held keys

    # save a snapshot before mutating. call before every edit operation.
    def _snap(self):
        state = (list(self.lines), self.cy, self.cx)
        if state == self._last_snap: return
        self._undo.append(state)
        self._redo.clear()
        self._last_snap = state

    def undo(self):
        if not self._undo: return
        self._redo.append((list(self.lines), self.cy, self.cx))
        self.lines, self.cy, self.cx = self._undo.pop()
        self._last_snap = None
        self.modified = True

    def redo(self):
        if not self._redo: return
        self._undo.append((list(self.lines), self.cy, self.cx))
        self.lines, self.cy, self.cx = self._redo.pop()
        self._last_snap = None
        self.modified = True

    def _detect_indent(self):
        # look at the first 200 lines and count tab vs space indentation.
        tabs = spaces = 0
        sizes = {}
        for line in self.lines[:200]:
            if line.startswith('\t'): tabs += 1
            elif line.startswith(' '):
                spaces += 1
                n = len(line) - len(line.lstrip(' '))
                if n: sizes[n] = sizes.get(n,0) + 1
        self.indent_char = '\t' if tabs > spaces else ' '
        if sizes:
            # most common indent size wins
            self.indent_size = min(sorted(sizes, key=sizes.get, reverse=True)[:1] or [4])
        else:
            self.indent_size = 4

    def load(self, path):
        self.filepath = path
        self.lang     = get_lang(path)
        try:
            self.lines = Path(path).read_text(errors='replace').split('\n')
            if not self.lines: self.lines = ['']
        except OSError:
            self.lines = ['']
        self.cy = self.cx = self.sy = self.sx = 0
        self.modified = False
        self._undo.clear(); self._redo.clear(); self._last_snap = None
        self._detect_indent()

    def save(self):
        if not self.filepath: return False
        try:
            Path(self.filepath).write_text('\n'.join(self.lines))
            self.modified = False
            return True
        except OSError:
            return False

    def insert(self, ch):
        self._snap()
        l = self.lines[self.cy]
        # auto-close brackets/quotes — insert pair and leave cursor between them
        if ch in _PAIRS and ch not in _CLOSE:
            closing = _PAIRS[ch]
            self.lines[self.cy] = l[:self.cx] + ch + closing + l[self.cx:]
            self.cx += 1; self.modified = True; return
        # skip over a closing bracket if it's already there
        if ch in _CLOSE and self.cx < len(l) and l[self.cx] == ch:
            self.cx += 1; return
        self.lines[self.cy] = l[:self.cx] + ch + l[self.cx:]
        self.cx += 1; self.modified = True

    def backspace(self):
        self._snap()
        l = self.lines[self.cy]
        # eat paired closing bracket when backspacing an opener
        if (self.cx > 0 and self.cx < len(l)
                and l[self.cx-1] in _PAIRS
                and l[self.cx] == _PAIRS[l[self.cx-1]]):
            self.lines[self.cy] = l[:self.cx-1] + l[self.cx+1:]
            self.cx -= 1; self.modified = True; return
        if self.cx > 0:
            self.lines[self.cy] = l[:self.cx-1] + l[self.cx:]
            self.cx -= 1; self.modified = True
        elif self.cy > 0:
            self.cx = len(self.lines[self.cy-1])
            self.lines[self.cy-1] += self.lines.pop(self.cy)
            self.cy -= 1; self.modified = True

    def delete_fwd(self):
        self._snap()
        l = self.lines[self.cy]
        if self.cx < len(l):
            self.lines[self.cy] = l[:self.cx] + l[self.cx+1:]
            self.modified = True
        elif self.cy < len(self.lines)-1:
            self.lines[self.cy] += self.lines.pop(self.cy+1)
            self.modified = True

    def newline(self):
        self._snap()
        l      = self.lines[self.cy]
        indent = len(l) - len(l.lstrip())
        # extra indent after lines ending in : (python) or { (c-like)
        if l.rstrip().endswith((':','{')):
            indent += self.indent_size
        self.lines[self.cy] = l[:self.cx]
        self.lines.insert(self.cy+1, ' '*indent + l[self.cx:])
        self.cy += 1; self.cx = indent; self.modified = True

    def tab(self):
        self._snap()
        if self.indent_char == '\t':
            self.insert('\t')
        else:
            for _ in range(self.indent_size): self.lines[self.cy]; self.cx  # keep cx aligned
            l = self.lines[self.cy]
            spaces = self.indent_size - (self.cx % self.indent_size)
            self.lines[self.cy] = l[:self.cx] + ' '*spaces + l[self.cx:]
            self.cx += spaces; self.modified = True

    def move(self, dy, dx):
        self.cy = max(0, min(len(self.lines)-1, self.cy+dy))
        if dx: self.cx = max(0, min(len(self.lines[self.cy]), self.cx+dx))
        else:  self.cx = min(self.cx, len(self.lines[self.cy]))

    def page(self, rows, d):
        self.cy = max(0, min(len(self.lines)-1, self.cy+d*rows))
        self.cx = min(self.cx, len(self.lines[self.cy]))

    def home(self):
        indent = len(self.lines[self.cy]) - len(self.lines[self.cy].lstrip())
        self.cx = indent if self.cx != indent else 0

    def end(self):  self.cx = len(self.lines[self.cy])

    def word_left(self):
        while self.cx > 0 and not self.lines[self.cy][self.cx-1].isalnum(): self.cx-=1
        while self.cx > 0 and self.lines[self.cy][self.cx-1].isalnum(): self.cx-=1

    def word_right(self):
        l = self.lines[self.cy]
        while self.cx < len(l) and not l[self.cx].isalnum(): self.cx+=1
        while self.cx < len(l) and l[self.cx].isalnum(): self.cx+=1

    def find_bracket_match(self):
        # returns (row, col) of matching bracket for the char under cursor, or None.
        if self.cy >= len(self.lines): return None
        l  = self.lines[self.cy]
        ch = l[self.cx:self.cx+1]
        if not ch: return None
        if ch in _OPEN_B:
            # search forward
            target = _MATCH[ch]; depth = 0
            for row in range(self.cy, len(self.lines)):
                start = self.cx+1 if row==self.cy else 0
                for col, c in enumerate(self.lines[row][start:], start):
                    if c == ch: depth += 1
                    elif c == target:
                        if depth == 0: return (row, col)
                        depth -= 1
        elif ch in _CLOSE_B:
            # search backward
            target = _MATCH[ch]; depth = 0
            for row in range(self.cy, -1, -1):
                end = self.cx if row==self.cy else len(self.lines[row])
                for col in range(end-1, -1, -1):
                    c = self.lines[row][col]
                    if c == ch: depth += 1
                    elif c == target:
                        if depth == 0: return (row, col)
                        depth -= 1
        return None


# --- FileTree ----------------------------------------------------------------

_SKIP = frozenset((
    '.git','__pycache__','.DS_Store','node_modules','.pytest_cache',
    '.mypy_cache','venv','.venv','.tox','.idea','.vscode','dist','build',
))

class FileTree:
    def __init__(self, root):
        self.root=Path(root); self.items=[]; self.selected=0; self.scroll=0
        self._open=set(); self.refresh()

    def refresh(self):
        self.items=[]
        self._walk(self.root,0)
        self.selected=min(self.selected,max(0,len(self.items)-1))

    def _walk(self,path,depth):
        try: entries=sorted(path.iterdir(),key=lambda p:(not p.is_dir(),p.name.lower()))
        except PermissionError: return
        for e in entries:
            if e.name in _SKIP or e.name.startswith('.'): continue
            self.items.append({'path':e,'depth':depth,'is_dir':e.is_dir(),
                               'expanded':str(e) in self._open})
            if e.is_dir() and str(e) in self._open: self._walk(e,depth+1)

    def toggle(self):
        if not self.items: return
        n=self.items[self.selected]
        if not n['is_dir']: return
        k=str(n['path'])
        self._open.discard(k) if k in self._open else self._open.add(k)
        self.refresh()

    def go_up(self):
        if self.root.parent==self.root: return
        self.root=self.root.parent; self.selected=self.scroll=0; self.refresh()

    def move(self,d): self.selected=max(0,min(len(self.items)-1,self.selected+d))
    def current(self): return self.items[self.selected] if self.items else None


# --- TermPanel ---------------------------------------------------------------
#
# not a PTY. blocking subprocess. if you need htop, use a real terminal.

class TermPanel:
    MAX_SCROLLBACK = 2000
    def __init__(self, cwd):
        self.cwd=Path(cwd); self.buf=deque(maxlen=self.MAX_SCROLLBACK)
        self.input=''; self.scroll=0; self.active=False
        self.buf.extend([f'  cwd: {cwd}', '  type a command, press Enter', ''])

    def run(self, cmd):
        if not cmd.strip(): return
        self.buf.append(f'$ {cmd}')
        try:
            r=subprocess.run(shlex.split(cmd),cwd=str(self.cwd),
                             capture_output=True,text=True,timeout=30,errors='replace')
            for line in (r.stdout+r.stderr).splitlines(): self.buf.append('  '+line)
            if r.returncode: self.buf.append(f'  [exit {r.returncode}]')
        except FileNotFoundError: self.buf.append(f'  {cmd.split()[0]}: command not found')
        except subprocess.TimeoutExpired: self.buf.append('  killed: timeout after 30s')
        except Exception as e: self.buf.append(f'  error: {e}')
        self.buf.append(''); self.scroll=len(self.buf)

    def type(self,ch): self.input+=ch
    def bs(self):      self.input=self.input[:-1]
    def up(self,n=3):  self.scroll=max(0,self.scroll-n)
    def dn(self,n=3):  self.scroll=min(len(self.buf),self.scroll+n)


# --- SmartBar ----------------------------------------------------------------
#
# unified floating input: search, path, commands, quick-open, grep, replace.

_CMDS = (
    ('save',       'write buffer to disk'),
    ('new',        'empty buffer'),
    ('help',       'keybinding reference'),
    ('outline',    'jump to function/class'),
    ('git status', 'short status'),
    ('git log',    'last 10 commits'),
    ('zen',        'toggle zen mode'),
    ('exit',       'quit'),
)

class SmartBar:
    SEARCH  = 's'   # search in file
    PATH    = 'p'   # go to folder
    CMD     = 'c'   # command palette
    OPEN    = 'o'   # quick-open file by name (Ctrl+P)
    GREP    = 'g'   # global grep across project
    REPLACE = 'r'   # find+replace in current file
    OUTLINE = 'u'   # outline / symbol search

    def __init__(self):
        self.mode=None; self.text=''; self.results=[]; self.idx=0
        # replace mode has a two-field input: find \0 replace
        self.replace_text = ''
        self.replace_field = 0   # 0=find, 1=replace

    def open(self,mode,prefill=''):
        self.mode=mode; self.text=prefill; self.results=[]
        self.idx=0; self.replace_text=''; self.replace_field=0

    def close(self): self.mode=None; self.text=''; self.results=[]
    def active(self): return self.mode is not None

    def type(self,ch):
        if self.mode==self.REPLACE and self.replace_field==1: self.replace_text+=ch
        else: self.text+=ch

    def bs(self):
        if self.mode==self.REPLACE and self.replace_field==1: self.replace_text=self.replace_text[:-1]
        else: self.text=self.text[:-1]

    def nav(self,d):
        if self.results: self.idx=(self.idx+d)%len(self.results)

    def update(self, ed, tree_root=None):
        q = self.text.lower()
        if self.mode == self.SEARCH:
            self.results = [f'{i+1:5d}  {l.rstrip()[:60]}'
                            for i,l in enumerate(ed.lines) if q and q in l.lower()]
        elif self.mode == self.CMD:
            self.results = [f'{c:<16} {d}' for c,d in _CMDS if not q or q in c]
        elif self.mode == self.OPEN and tree_root:
            # walk the filesystem and fuzzy-match filenames
            self.results = []
            try:
                for p in sorted(Path(tree_root).rglob('*'))[:2000]:
                    if p.is_file() and not any(s in p.parts for s in _SKIP):
                        name = p.name.lower()
                        if not q or all(c in name for c in q):
                            self.results.append(str(p))
                            if len(self.results) >= 50: break
            except Exception: pass
        elif self.mode == self.GREP and tree_root and q:
            # grep -rn is faster than rolling our own
            self.results = []
            try:
                r = subprocess.run(
                    ['grep','-rn','--include=*','--color=never','-I',q,str(tree_root)],
                    capture_output=True,text=True,timeout=10,errors='replace')
                for line in r.stdout.splitlines()[:100]:
                    # trim the root prefix so lines don't scroll off screen
                    self.results.append(line.replace(str(tree_root)+'/',''))
            except Exception: pass
        elif self.mode == self.OUTLINE:
            entries = build_outline(ed.lines, ed.lang)
            self.results = [f'{ln+1:5d}  {label}' for ln,label in entries
                            if not q or q in label.lower()]
        elif self.mode == self.REPLACE:
            if self.text:
                self.results = [f'{i+1:5d}  {l.rstrip()[:58]}'
                                for i,l in enumerate(ed.lines) if self.text.lower() in l.lower()]

    def hit_line(self):
        if self.results and self.mode in (self.SEARCH, self.OUTLINE, self.REPLACE):
            try: return int(self.results[self.idx].strip().split()[0])-1
            except: return None

    def hit_cmd(self):
        if self.mode==self.CMD and self.results: return self.results[self.idx].split()[0]
        return self.text.strip()

    def hit_file(self):
        if self.mode==self.OPEN and self.results: return self.results[self.idx]
        return None

    def hit_grep(self):
        # returns (filepath, line_number) or None
        if self.mode==self.GREP and self.results:
            r = self.results[self.idx]
            m = re.match(r'^([^:]+):(\d+):', r)
            return (m.group(1), int(m.group(2))-1) if m else None
        return None


# --- help text ---------------------------------------------------------------

HELP = """\
  vs-cli — keybindings

  F5            → explorer          Ctrl+P        quick open file
  F6            → editor            Ctrl+Shift+F  grep in project
  Shift+F6      command palette     Ctrl+O        outline / symbols
  F9 → A        open terminal       F11           zen mode
  F9 → C        close terminal      Alt+R         find + replace

  Ctrl+S        save                Ctrl+Z        undo
  Ctrl+Q        quit                Ctrl+Y        redo
  Alt+S         search in file
  Alt+W         go to folder

  editor:
    ↑↓←→        move cursor         Ctrl+←/→      word jump
    Home/End    smart home/end      PgUp/Dn       scroll fast
    Tab         indent (auto-detect spaces vs tabs)
    Enter       newline + smart indent

  explorer:
    ↑↓ Enter    navigate/open       Backspace     parent dir

  terminal:
    Enter       run command         ↑↓            scroll output
    Esc         focus editor

  gutter:  + added   ~ modified   - deleted (git diff)

  any key closes this
""".splitlines()


# --- VsCli -------------------------------------------------------------------
#
# the main class. render() builds one big string and blasts it to stdout.
# flicker-free because the write is effectively atomic at normal frame rates.
#
# layout (normal mode):
#   row 0:           title bar
#   rows 1..EH:      [git-gutter | sidebar | divider | lnum | editor]
#   row EH+1:        terminal separator  (if open)
#   rows EH+2..:     terminal panel      (if open)
#   last row:        status bar
#
# zen mode hides sidebar, gutter, and status bar.

class VsCli:
    SW     = 26   # sidebar width (hidden in zen mode)
    LW     = 5    # line number gutter
    GW     = 1    # git gutter width (1 char)
    TERM_H = 12   # terminal panel height

    def __init__(self, root):
        self.t    = Terminal()
        self.tree = FileTree(root)
        self.ed   = EditorState()
        self.bar  = SmartBar()
        self.trm  = TermPanel(root)
        self.focus      = 'editor'
        self.msg        = ''
        self.msg_err    = False
        self.helpscreen = False
        self.running    = True
        self.zen        = False   # zen mode: no sidebar, no statusbar
        self._f9        = False
        self._git_marks = {}      # line→'+','~','-' from git diff
        self._outline_open = False

    def _sidebar_w(self): return 0 if self.zen else self.SW
    def _gutter_w(self):  return 0 if self.zen else self.GW
    def _eh(self):
        base = self.t.height - (1 if self.zen else 2)
        if self.trm.active: base -= self.TERM_H+1
        return max(4, base)
    def _ew(self):
        return max(10, self.t.width - self._sidebar_w() - self._gutter_w() - self.LW - 2)
    def _es(self):   # editor start column
        return self._sidebar_w() + self._gutter_w() + 1 + self.LW

    def _refresh_git(self):
        self._git_marks = git_diff_markers(self.ed.filepath, self.tree.root)

    # -------------------------------------------------------------------------
    # rendering
    # -------------------------------------------------------------------------

    def render(self):
        t  = self.t
        W  = t.width
        EH = self._eh()
        EW = self._ew()
        ES = self._es()
        SW = self._sidebar_w()
        GW = self._gutter_w()
        ed = self.ed
        out = [t.home]

        # title bar (always shown)
        fname = Path(ed.filepath).name if ed.filepath else ''
        title = f' vs-cli  {"—  "+fname+("*" if ed.modified else "") if fname else ""}'
        if self.zen: title += '   [zen]'
        out.append(bg(234)+fg(245)+_B + title.ljust(W)[:W] + _R)

        if not self.zen:
            # sidebar header
            exp = self.focus=='explorer'
            out.append(t.move(1,0)+(bg(235)+fg(252)+_B if exp else bg(233)+fg(244))
                       +' EXPLORER'.ljust(SW)[:SW]+_R)

            # file tree
            items=self.tree.items
            for i in range(EH-1):
                row=i+2; idx=self.tree.scroll+i
                if idx>=len(items):
                    out.append(t.move(row,0)+bg(233)+' '*SW+_R); continue
                n=items[idx]; sel=(idx==self.tree.selected and exp)
                lbl=('  '*n['depth']+file_icon(n['path'].name,n['is_dir'],n['expanded'])
                     +n['path'].name)[:SW-1].ljust(SW)
                sty=(bg(32)+fg(255) if sel else bg(233)+fg(250) if n['is_dir'] else bg(233)+fg(244))
                out.append(t.move(row,0)+sty+lbl+_R)

            # git gutter (1 char wide, between sidebar and line numbers)
            gutter_col = SW+1
            for i in range(EH):
                ln = ed.sy+i+1
                mark = self._git_marks.get(ln)
                if   mark=='+': gchar=fg(71)+'▌'+_R    # green  — added
                elif mark=='~': gchar=fg(220)+'▌'+_R   # yellow — modified
                elif mark=='-': gchar=fg(196)+'▾'+_R   # red    — deleted below
                else:           gchar=bg(234)+' '+_R
                out.append(t.move(i+1, gutter_col)+gchar)

            # divider
            div_col = SW+GW+1
            for r in range(1,t.height-1):
                out.append(t.move(r,div_col)+bg(236)+fg(238)+'│'+_R)

        # line number gutter
        ln_col = SW+GW+1+int(not self.zen) if not self.zen else 1
        for i in range(EH):
            ln=ed.sy+i+1
            if ln<=len(ed.lines):
                cur=(ed.sy+i==ed.cy)
                out.append(t.move(i+1,ln_col)
                           +(bg(235)+_B+fg(244) if cur else bg(234)+fg(238))
                           +f'{ln:>{self.LW-1}} '+_R)
            else:
                out.append(t.move(i+1,ln_col)+bg(234)+' '*self.LW+_R)

        # bracket match position — find it once per render
        br_match = self.ed.find_bracket_match() if self.focus=='editor' else None

        # editor content
        if self.helpscreen:
            for i in range(EH):
                txt=HELP[i] if i<len(HELP) else ''
                out.append(t.move(i+1,ES)+bg(235)+fg(252)+txt[:EW].ljust(EW)+_R)
        else:
            for i in range(EH):
                li=ed.sy+i; lbg=bg(235) if li==ed.cy else bg(234)
                if li<len(ed.lines):
                    raw=ed.lines[li]; vis=raw[ed.sx:ed.sx+EW]
                    hl=highlight(vis, ed.lang)
                    # bracket match highlight — overlay on top of syntax color
                    if br_match and br_match[0]==li:
                        mc=br_match[1]-ed.sx
                        if 0<=mc<EW:
                            ch=vis[mc:mc+1] or ' '
                            # re-inject highlight at that char position
                            hl=hl  # we'll handle this in cursor render below
                    out.append(t.move(i+1,ES)+lbg+hl+lbg+' '*max(0,EW-len(vis))+_R)
                else:
                    out.append(t.move(i+1,ES)+bg(234)+' '*EW+_R)

        # cursor block
        if self.focus=='editor' and not self.helpscreen and not self.bar.active():
            sr=ed.cy-ed.sy+1; sc=ed.cx-ed.sx+ES
            if 1<=sr<=EH and ES<=sc<ES+EW:
                ch=(ed.lines[ed.cy][ed.cx:ed.cx+1] if ed.cy<len(ed.lines) else '') or ' '
                out.append(t.move(sr,sc)+bg(7)+fg(0)+ch+_R)
            # bracket match highlight
            if br_match:
                br,bc=br_match; bsr=br-ed.sy+1; bsc=bc-ed.sx+ES
                if 1<=bsr<=EH and ES<=bsc<ES+EW:
                    bch=(ed.lines[br][bc:bc+1]) or ' '
                    out.append(t.move(bsr,bsc)+bg(94)+fg(220)+_B+bch+_R)

        # sticky scroll — show the nearest enclosing function/class header
        # at the top of the editor if it's scrolled off screen.
        if not self.helpscreen and not self.zen and ed.sy > 0:
            sticky = self._sticky_line()
            if sticky is not None:
                stub = ed.lines[sticky][ed.sx:ed.sx+EW]
                out.append(t.move(1,ES)+bg(237)+fg(246)+_B
                           +highlight(stub,ed.lang)[:EW].ljust(EW)+_R)

        # terminal panel
        if self.trm.active:
            self._draw_terminal(out,EH,W)

        # status bar (hidden in zen mode)
        if not self.zen:
            mode={'editor':'INSERT','explorer':'EXPLORE','terminal':'TERMINAL'}.get(self.focus,'')
            lang=ed.lang.upper() if ed.filepath else ''
            pos=f'Ln {ed.cy+1}, Col {ed.cx+1}'
            indent_info=f'{"tab" if ed.indent_char==chr(9) else f"{ed.indent_size}spc"}'
            left=f'  {mode}  ⎇ main  {self.msg[:48]}'
            right=f' {pos}  {indent_info}  {lang}  UTF-8  '
            mid=max(0,W-len(left)-len(right))
            fbg=26 if self.focus in ('editor','terminal') else 22
            mc=fg(203) if self.msg_err else fg(252)
            out.append(t.move(t.height-1,0)
                       +bg(fbg)+_B+fg(255)+left+mc+' '*mid+fg(230)+right+_R)

        # floating bar (always on top)
        if self.bar.active():
            self._draw_bar(out,W,t.height)

        sys.stdout.write(''.join(out))
        sys.stdout.flush()

    def _sticky_line(self):
        # find the last function/class definition above the current viewport.
        if self.ed.lang not in ('py','js','ts'): return None
        pat = (re.compile(r'^\s*(def|class)\s+') if self.ed.lang=='py'
               else re.compile(r'^\s*(function|class|async function)\s+'))
        for i in range(self.ed.sy-1, -1, -1):
            if i < len(self.ed.lines) and pat.match(self.ed.lines[i]):
                return i
        return None

    def _draw_terminal(self,out,EH,W):
        t=self.t; TH=self.TERM_H; TW=W-self._sidebar_w()-2; tp=EH+2
        label=' TERMINAL '
        sep=(('╌'*((TW-len(label))//2))+label+('╌'*((TW-len(label)+1)//2)))[:TW]
        out.append(t.move(tp-1,self._sidebar_w()+1)
                   +bg(232)+(fg(39) if self.focus=='terminal' else fg(238))+sep+_R)
        buf=list(self.trm.buf); start=max(0,self.trm.scroll-(TH-1))
        view=buf[start:start+TH-1]
        for i in range(TH-1):
            txt=view[i] if i<len(view) else ''
            out.append(t.move(tp+i,self._sidebar_w()+1)+bg(232)+fg(245)+txt[:TW].ljust(TW)+_R)
        prompt=f' $ {self.trm.input}_'
        isty=bg(235)+fg(255) if self.focus=='terminal' else bg(232)+fg(240)
        out.append(t.move(tp+TH-1,self._sidebar_w()+1)+isty+prompt[:TW].ljust(TW)+_R)

    def _draw_bar(self,out,W,H):
        b=self.bar; t=self.t
        SW=self._sidebar_w()
        if   b.mode==SmartBar.SEARCH:  bw,bx,by=W-SW-4,SW+2,1;           title=' SEARCH IN FILE '
        elif b.mode==SmartBar.PATH:    bw=min(64,W-4);bx=max(0,W//2-bw//2);by=H//2-3; title=' GO TO FOLDER '
        elif b.mode==SmartBar.OPEN:    bw=min(70,W-4);bx=max(0,W//2-bw//2);by=H//2-5; title=' QUICK OPEN '
        elif b.mode==SmartBar.GREP:    bw=min(80,W-4);bx=max(0,W//2-bw//2);by=2;       title=' GREP IN PROJECT '
        elif b.mode==SmartBar.REPLACE: bw=min(64,W-4);bx=max(0,W//2-bw//2);by=H//2-4; title=' FIND + REPLACE '
        elif b.mode==SmartBar.OUTLINE: bw=min(50,W-4);bx=max(0,W//2-bw//2);by=H//2-5; title=' OUTLINE '
        else:                          bw=min(58,W-4);bx=max(0,W//2-bw//2);by=H//2-4; title=' COMMAND PALETTE '

        iw=bw-2
        top='╭'+title.center(iw,'─')+'╮'
        sep='├'+'─'*iw+'┤'
        bot='╰'+'─'*iw+'╯'

        out.append(t.move(by,  bx)+bg(236)+_B+fg(39) +top[:bw]+_R)

        # replace mode has two input fields
        if b.mode==SmartBar.REPLACE:
            find_txt    = f'  find:    {b.text}_' if b.replace_field==0 else f'  find:    {b.text}'
            replace_txt = f'  replace: {b.replace_text}_' if b.replace_field==1 else f'  replace: {b.replace_text}'
            out.append(t.move(by+1,bx)+bg(236)+fg(255)+'│'+find_txt[:iw].ljust(iw)+'│'+_R)
            out.append(t.move(by+2,bx)+bg(236)+fg(255)+'│'+replace_txt[:iw].ljust(iw)+'│'+_R)
            out.append(t.move(by+3,bx)+bg(236)+fg(238)+sep[:bw]+_R)
            row_off=4
        else:
            out.append(t.move(by+1,bx)+bg(236)+fg(255)+'│'+f'  {b.text}_'[:iw].ljust(iw)+'│'+_R)
            out.append(t.move(by+2,bx)+bg(236)+fg(238)+sep[:bw]+_R)
            row_off=3

        rows=b.results[:8]
        for i,r in enumerate(rows):
            sty=bg(32)+fg(255) if i==b.idx else bg(236)+fg(245)
            out.append(t.move(by+row_off+i,bx)+sty+'│ '+r[:iw-4].ljust(iw-4)+' │'+_R)
        for i in range(len(rows),5):
            out.append(t.move(by+row_off+i,bx)+bg(236)+'│'+' '*iw+'│'+_R)

        hints={SmartBar.SEARCH: '  ↑↓ select · Enter jump · Esc cancel',
               SmartBar.PATH:   '  Enter navigate · Esc cancel',
               SmartBar.OPEN:   '  ↑↓ select · Enter open · Esc cancel',
               SmartBar.GREP:   '  ↑↓ select · Enter open · Esc cancel',
               SmartBar.REPLACE:'  Tab switch fields · Enter replace all · Esc cancel',
               SmartBar.OUTLINE:'  ↑↓ select · Enter jump · Esc cancel',
               SmartBar.CMD:    '  Enter run · ↑↓ select · Esc cancel'}
        end=by+row_off+max(len(rows),5)
        out.append(t.move(end,  bx)+bg(236)+fg(238)+'│'+hints.get(b.mode,'')[:iw].ljust(iw)+'│'+_R)
        out.append(t.move(end+1,bx)+bg(236)+fg(39) +bot[:bw]+_R)

    # -------------------------------------------------------------------------
    # scroll sync
    # -------------------------------------------------------------------------

    def _sync(self):
        ed,EH,EW=self.ed,self._eh(),self._ew()
        if ed.cy<ed.sy:          ed.sy=ed.cy
        elif ed.cy>=ed.sy+EH:    ed.sy=ed.cy-EH+1
        if ed.cx<ed.sx:          ed.sx=ed.cx
        elif ed.cx>=ed.sx+EW:    ed.sx=ed.cx-EW+1
        vis=EH-1
        if self.tree.selected<self.tree.scroll:
            self.tree.scroll=self.tree.selected
        elif self.tree.selected>=self.tree.scroll+vis:
            self.tree.scroll=self.tree.selected-vis+1

    # -------------------------------------------------------------------------
    # input dispatch
    # -------------------------------------------------------------------------

    def handle(self,key):
        if self.helpscreen: self.helpscreen=False; return

        raw=str(key)

        # F9 chord
        if key.name=='KEY_F9': self._f9=True; return
        if self._f9:
            self._f9=False; ch=raw.lower()
            if ch=='a': self.trm.active=True;self.focus='terminal';self.msg='terminal open'; return
            if ch=='c':
                self.trm.active=False
                if self.focus=='terminal': self.focus='editor'
                self.msg='terminal closed'; return

        # terminal
        if self.focus=='terminal':
            match key.name:
                case 'KEY_ESCAPE':    self.focus='editor'
                case 'KEY_ENTER':     self.trm.run(self.trm.input); self.trm.input=''
                case 'KEY_BACKSPACE': self.trm.bs()
                case 'KEY_UP':        self.trm.up()
                case 'KEY_DOWN':      self.trm.dn()
                case _:
                    if not key.is_sequence and key: self.trm.type(raw)
            return

        # smart bar
        if self.bar.active():
            match key.name:
                case 'KEY_ESCAPE': self.bar.close()
                case 'KEY_ENTER':  self._bar_confirm()
                case 'KEY_UP':     self.bar.nav(-1)
                case 'KEY_DOWN':   self.bar.nav(1)
                case 'KEY_TAB':
                    if self.bar.mode==SmartBar.REPLACE:
                        self.bar.replace_field=1-self.bar.replace_field
                case 'KEY_BACKSPACE': self.bar.bs(); self.bar.update(self.ed,self.tree.root)
                case _:
                    if not key.is_sequence and key:
                        self.bar.type(raw); self.bar.update(self.ed,self.tree.root)
            return

        # --- global shortcuts ---

        if key.name=='KEY_F5':    self.focus='explorer'; self.msg='arrows+Enter, Backspace=parent'; return
        if key.name=='KEY_F6':    self.focus='editor';   self.msg=''; return
        if key.name=='KEY_F11':   self.zen=not self.zen; self.msg='zen mode on' if self.zen else 'zen mode off'; return
        if raw in ('\x1b[17;2~','\x1b[1;2Q'):           # Shift+F6 → command palette
            self.bar.open(SmartBar.CMD); self.bar.update(self.ed,self.tree.root); return
        if raw in ('\x1bs','\x1bS'):                    # Alt+S → search
            self.bar.open(SmartBar.SEARCH); self.bar.update(self.ed); return
        if raw in ('\x1bw','\x1bW'):                    # Alt+W → folder
            self.bar.open(SmartBar.PATH,str(self.tree.root)); return
        if raw in ('\x1br','\x1bR'):                    # Alt+R → find+replace
            self.bar.open(SmartBar.REPLACE); self.bar.update(self.ed); return
        if raw == '\x0f':                               # Ctrl+O → outline
            self.bar.open(SmartBar.OUTLINE); self.bar.update(self.ed); return
        if raw == '\x10':                               # Ctrl+P → quick open
            self.bar.open(SmartBar.OPEN); self.bar.update(self.ed,self.tree.root); return
        if raw == '\x06':                               # Ctrl+F → grep (Ctrl+Shift+F is tricky; this works)
            self.bar.open(SmartBar.GREP); return
        if raw == '\x13':                               # Ctrl+S → save
            if self.ed.save():
                self._refresh_git()
                self.msg=f'saved — {Path(self.ed.filepath).name}'
            else: self.msg='nothing to save'
            return
        if raw == '\x1a': self.ed.undo(); self.msg='undo'; return   # Ctrl+Z
        if raw == '\x19': self.ed.redo(); self.msg='redo'; return   # Ctrl+Y
        if raw == '\x11': self.running=False; return                # Ctrl+Q

        # explorer
        if self.focus=='explorer':
            match key.name:
                case 'KEY_UP':        self.tree.move(-1)
                case 'KEY_DOWN':      self.tree.move(1)
                case 'KEY_BACKSPACE': self.tree.go_up(); self.msg=f'↑ {self.tree.root}'
                case 'KEY_ENTER':
                    n=self.tree.current()
                    if n:
                        if n['is_dir']: self.tree.toggle()
                        else:
                            self.ed.load(str(n['path'])); self._refresh_git()
                            self.msg=f'opened {n["path"].name}'; self.focus='editor'
            return

        # editor
        if self.focus=='editor':
            ed=self.ed
            match key.name:
                case 'KEY_UP':        ed.move(-1,0)
                case 'KEY_DOWN':      ed.move(1,0)
                case 'KEY_LEFT':      ed.move(0,-1)
                case 'KEY_RIGHT':     ed.move(0,1)
                case 'KEY_HOME':      ed.home()
                case 'KEY_END':       ed.end()
                case 'KEY_PGUP':      ed.page(self._eh()-2,-1)
                case 'KEY_PGDOWN':    ed.page(self._eh()-2,1)
                case 'KEY_ENTER':     ed.newline()
                case 'KEY_BACKSPACE': ed.backspace()
                case 'KEY_DELETE':    ed.delete_fwd()
                case 'KEY_TAB':       ed.tab()
                case _:
                    if raw=='\x1b[1;5D': ed.word_left();  return
                    if raw=='\x1b[1;5C': ed.word_right(); return
                    if not key.is_sequence and key: ed.insert(raw)

    def _bar_confirm(self):
        b=self.bar
        if b.mode in (SmartBar.SEARCH, SmartBar.OUTLINE):
            ln=b.hit_line()
            if ln is not None: self.ed.cy=ln; self.ed.cx=0; self.msg=f'line {ln+1}'
            b.close(); self.focus='editor'

        elif b.mode==SmartBar.PATH:
            p=Path(b.text.strip()).expanduser()
            if p.is_dir():
                self.tree.root=p; self.tree.selected=self.tree.scroll=0
                self.tree._open.clear(); self.tree.refresh()
                self.trm.cwd=p; self.msg=f'→ {p}'; self.focus='explorer'
            else: self.msg=f'not a directory: {p}'; self.msg_err=True
            b.close()

        elif b.mode==SmartBar.OPEN:
            f=b.hit_file()
            if f:
                self.ed.load(f); self._refresh_git()
                self.msg=f'opened {Path(f).name}'; self.focus='editor'
            b.close()

        elif b.mode==SmartBar.GREP:
            hit=b.hit_grep()
            if hit:
                fpath, ln = hit
                full = Path(self.tree.root)/fpath
                if not full.exists(): full=Path(fpath)
                if full.exists():
                    self.ed.load(str(full)); self._refresh_git()
                    self.ed.cy=ln; self.ed.cx=0; self.msg=f'opened {full.name}:{ln+1}'
                    self.focus='editor'
            b.close()

        elif b.mode==SmartBar.REPLACE:
            # replace all occurrences of find_text with replace_text
            find=b.text; rep=b.replace_text
            if find:
                count=0
                new_lines=[]
                for line in self.ed.lines:
                    new_lines.append(line.replace(find,rep))
                    count+=line.count(find)
                if count:
                    self.ed._snap()
                    self.ed.lines=new_lines; self.ed.modified=True
                    self.msg=f'replaced {count} occurrence{"s" if count!=1 else ""}'
                else: self.msg='no matches'
            b.close()

        elif b.mode==SmartBar.CMD:
            cmd=b.hit_cmd(); b.close(); self._exec(cmd)

    def _exec(self,cmd):
        cmd=cmd.lower().strip()
        if   cmd=='exit': self.running=False
        elif cmd=='save':
            if self.ed.save(): self._refresh_git(); self.msg=f'saved — {Path(self.ed.filepath).name}'
            else: self.msg='nothing to save'
        elif cmd=='new':
            self.ed.filepath='untitled.py'; self.ed.lines=['']
            self.ed.cx=self.ed.cy=0; self.ed.modified=True
            self.ed.lang='py'; self.focus='editor'; self.msg='new buffer'
        elif cmd=='help': self.helpscreen=True
        elif cmd=='zen':  self.zen=not self.zen; self.msg='zen '+('on' if self.zen else 'off')
        elif cmd=='outline':
            self.bar.open(SmartBar.OUTLINE); self.bar.update(self.ed)
        elif cmd in ('git status','git log'):
            args=cmd.split()[1:]
            extra=['--oneline','-10'] if args[0]=='log' else ['--short']
            try:
                r=subprocess.run(['git','-C',str(self.tree.root)]+args+extra,
                                 capture_output=True,text=True,timeout=5)
                self.msg=r.stdout.strip().replace('\n','  |  ')[:60] or 'clean'
            except: self.msg='git not found'
        else: self.msg=f'unknown: {cmd}'; self.msg_err=True

    # -------------------------------------------------------------------------
    # main loop
    # -------------------------------------------------------------------------

    def run(self):
        t=self.t
        with t.fullscreen(), t.hidden_cursor(), t.raw():
            sys.stdout.write(t.clear); sys.stdout.flush()
            for n in self.tree.items:
                if not n['is_dir']:
                    self.ed.load(str(n['path'])); self._refresh_git()
                    self.focus='editor'; break
            while self.running:
                self._sync(); self.render()
                key=t.inkey(timeout=0.05)
                if key: self.msg_err=False; self.msg=''; self.handle(key)
            sys.stdout.write(t.clear+t.home); sys.stdout.flush()
        print('\nvs-cli: goodbye\n')


def main():
    root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
    if not root.exists(): sys.exit(f'error: {root}: no such file or directory')
    app=VsCli(root.parent if root.is_file() else root)
    if root.is_file(): app.ed.load(str(root)); app._refresh_git(); app.focus='editor'
    app.run()


if __name__=='__main__':
    main()
