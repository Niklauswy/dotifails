"""Small line-based syntax highlighter shared by the code view and Markdown fences.

Colours come from the active theme's editor palette (``external.palette``), so a
theme change recolours code exactly like it recolours the terminal and nvim.
"""
from dataclasses import dataclass, field
from html import escape
import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

from theme_tokens import color, tokens

WORD = re.compile(r'[A-Za-z_$][\w$]*')
NUMBER = re.compile(r'0[xXbBoO][0-9a-fA-F_]+|\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?')
SHELL_VAR = re.compile(r'\$\{[^}]*\}|\$[A-Za-z_]\w*|\$[0-9@#?*!-]')
KEY = re.compile(r'^\s*(?:-\s+)?["\']?[\w./-]+["\']?(?=\s*[:=])')
CSS_PROP = re.compile(r'[\w-]+(?=\s*:)')
TAG = re.compile(r'</?[A-Za-z][\w:-]*|/?>')
HEX_COLOR = re.compile(r'#[0-9a-fA-F]{3,8}\b')

C_KEYWORDS = ('if else for while do switch case break continue return goto default struct union enum typedef static const extern '
              'sizeof volatile inline namespace using template typename class public private protected virtual override final '
              'new delete try catch throw throws import package interface extends implements abstract synchronized '
              'fn let mut pub impl trait use mod match loop where move async await dyn ref crate self super as in '
              'func var type range chan go defer select map fallthrough void int char long short float double bool unsigned signed '
              'string i8 i16 i32 i64 u8 u16 u32 u64 usize isize f32 f64 str').split()
JS_KEYWORDS = ('const let var function return if else for while do switch case break continue default new delete typeof instanceof '
               'void this class extends super import export from as async await yield try catch finally throw in of static get set '
               'interface type enum implements public private protected readonly abstract declare namespace module').split()
PY_KEYWORDS = ('and as assert async await break class continue def del elif else except finally for from global if import in is '
               'lambda nonlocal not or pass raise return try while with yield match case self cls').split()
SH_KEYWORDS = ('if then else elif fi for while until do done case esac in function select time return exit break continue local '
               'export readonly declare unset set shift source alias echo cd test').split()
LUA_KEYWORDS = 'and break do else elseif end for function goto if in local not or repeat return then until while'.split()
SQL_KEYWORDS = ('select from where insert into values update set delete create table drop alter add index join left right inner outer '
                'on group by order having limit offset union as and or not null is in like between distinct primary key foreign '
                'references default unique count sum avg min max case when then else end').split()
CONSTANTS = 'true false null nil none None True False undefined NaN Infinity NULL TRUE FALSE'.split()


@dataclass
class Language:
    keywords: frozenset = frozenset()
    line_comments: tuple = ()
    block: tuple = ()
    quotes: str = '"\''
    triple: bool = False
    multiline_quote: str = ''
    case_insensitive: bool = False
    shell_vars: bool = False
    keys: bool = False
    css: bool = False
    markup: bool = False
    constants: frozenset = field(default_factory=lambda: frozenset(CONSTANTS))


def _lang(words, **options):
    return Language(keywords=frozenset(words), **options)


LANGUAGES = {
    'python': _lang(PY_KEYWORDS, line_comments=('#',), triple=True),
    'javascript': _lang(JS_KEYWORDS, line_comments=('//',), block=('/*', '*/'), quotes='"\'`', multiline_quote='`'),
    'clike': _lang(C_KEYWORDS, line_comments=('//',), block=('/*', '*/')),
    'shell': _lang(SH_KEYWORDS, line_comments=('#',), shell_vars=True),
    'lua': _lang(LUA_KEYWORDS, line_comments=('--',), block=('--[[', ']]')),
    'sql': _lang(SQL_KEYWORDS, line_comments=('--',), block=('/*', '*/'), case_insensitive=True),
    'json': _lang((), keys=True),
    'config': _lang((), line_comments=('#', ';'), keys=True),
    'css': _lang('important media import charset keyframes font-face supports'.split(), block=('/*', '*/'), css=True),
    'markup': _lang((), block=('<!--', '-->'), markup=True),
    'plain': _lang(()),
}
EXTENSIONS = {
    '.py': 'python', '.pyw': 'python',
    '.js': 'javascript', '.jsx': 'javascript', '.ts': 'javascript', '.tsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
    '.c': 'clike', '.h': 'clike', '.cpp': 'clike', '.hpp': 'clike', '.cc': 'clike', '.java': 'clike', '.rs': 'clike', '.go': 'clike',
    '.qml': 'javascript', '.kt': 'clike', '.swift': 'clike', '.cs': 'clike', '.php': 'clike',
    '.sh': 'shell', '.bash': 'shell', '.zsh': 'shell', '.fish': 'shell', '.env': 'config',
    '.lua': 'lua', '.sql': 'sql', '.json': 'json', '.jsonc': 'json',
    '.yaml': 'config', '.yml': 'config', '.toml': 'config', '.ini': 'config', '.conf': 'config', '.cfg': 'config',
    '.desktop': 'config', '.service': 'config',
    '.css': 'css', '.scss': 'css', '.html': 'markup', '.htm': 'markup', '.xml': 'markup', '.svg': 'markup',
}
FENCES = {'py': 'python', 'python': 'python', 'js': 'javascript', 'javascript': 'javascript', 'ts': 'javascript',
          'typescript': 'javascript', 'jsx': 'javascript', 'tsx': 'javascript', 'c': 'clike', 'cpp': 'clike', 'c++': 'clike',
          'java': 'clike', 'rust': 'clike', 'rs': 'clike', 'go': 'clike', 'bash': 'shell', 'sh': 'shell', 'shell': 'shell',
          'zsh': 'shell', 'fish': 'shell', 'console': 'shell', 'lua': 'lua', 'sql': 'sql', 'json': 'json', 'yaml': 'config',
          'yml': 'config', 'toml': 'config', 'ini': 'config', 'css': 'css', 'scss': 'css', 'html': 'markup', 'xml': 'markup',
          'qml': 'javascript', 'kotlin': 'clike'}


def language_for_path(path):
    from pathlib import Path
    return EXTENSIONS.get(Path(path).suffix.lower(), 'plain')


def language_for_fence(name):
    return FENCES.get((name or '').strip().lower().split()[0] if (name or '').strip() else '', 'plain')


def tokenize(line, language, state=None):
    """Spans ``(start, end, kind)`` of one line, and the state carried to the next one."""
    config = LANGUAGES[language]
    line = line[:4000]
    spans, i, n = [], 0, len(line)
    if state:
        kind, end = state
        j = line.find(end)
        if j < 0:
            return [(0, n, kind)] if n else [], state
        spans.append((0, j + len(end), kind))
        i, state = j + len(end), None
    if config.keys and not config.markup:
        found = KEY.match(line)
        if found and language == 'json':
            pass  # keys are strings in JSON: handled with the quote below
        elif found:
            spans.append((found.start(), found.end(), 'key'))
            i = found.end()
    keywords = config.keywords
    while i < n:
        ch = line[i]
        comment = next((c for c in config.line_comments if line.startswith(c, i)), None)
        if comment and not (language == 'shell' and i and line[i - 1] in '$\\') and not (language == 'config' and comment == ';' and i):
            spans.append((i, n, 'comment'))
            return spans, None
        if config.block and line.startswith(config.block[0], i):
            j = line.find(config.block[1], i + len(config.block[0]))
            if j < 0:
                spans.append((i, n, 'comment'))
                return spans, ('comment', config.block[1])
            spans.append((i, j + len(config.block[1]), 'comment'))
            i = j + len(config.block[1])
            continue
        if ch in config.quotes and not config.markup:
            triple = config.triple and line.startswith(ch * 3, i)
            quote = ch * 3 if triple else ch
            j = i + len(quote)
            while j < n and not line.startswith(quote, j):
                j += 2 if line[j] == '\\' else 1
            if j >= n:
                spans.append((i, n, 'string'))
                return spans, (('string', quote) if triple or ch == config.multiline_quote else None)
            end = j + len(quote)
            kind = 'key' if language == 'json' and line[end:].lstrip().startswith(':') else 'string'
            spans.append((i, end, kind))
            i = end
            continue
        if config.markup:
            found = TAG.match(line, i)
            if found:
                spans.append((found.start(), found.end(), 'keyword'))
                i = found.end()
                continue
            if ch in '"\'':
                j = line.find(ch, i + 1)
                j = n - 1 if j < 0 else j
                spans.append((i, j + 1, 'string'))
                i = j + 1
                continue
            attribute = re.compile(r'[\w:-]+(?==)').match(line, i)
            if attribute:
                spans.append((attribute.start(), attribute.end(), 'key'))
                i = attribute.end()
                continue
            i += 1
            continue
        if config.shell_vars and ch == '$':
            found = SHELL_VAR.match(line, i)
            if found:
                spans.append((found.start(), found.end(), 'constant'))
                i = found.end()
                continue
        if config.css:
            found = CSS_PROP.match(line, i) if ch.isalpha() or ch == '-' else None
            if found and line[found.end():].lstrip().startswith(':') and '{' not in line[:i] or found and i == len(line) - len(line.lstrip()):
                spans.append((found.start(), found.end(), 'key'))
                i = found.end()
                continue
            color_hex = HEX_COLOR.match(line, i) if ch == '#' else None
            if color_hex:
                spans.append((color_hex.start(), color_hex.end(), 'number'))
                i = color_hex.end()
                continue
            if ch == '@':
                found = WORD.match(line, i + 1)
                if found:
                    spans.append((i, found.end(), 'keyword'))
                    i = found.end()
                    continue
        if ch.isdigit():
            found = NUMBER.match(line, i)
            spans.append((found.start(), found.end(), 'number'))
            i = found.end()
            continue
        if ch.isalpha() or ch in '_$':
            found = WORD.match(line, i)
            word = found.group()
            key = word.lower() if config.case_insensitive else word
            kind = None
            if key in keywords:
                kind = 'keyword'
            elif word in config.constants:
                kind = 'constant'
            elif line[found.end():found.end() + 1] == '(':
                kind = 'function'
            elif word[0].isupper() and len(word) > 1 and not word.isupper():
                kind = 'type'
            elif word.isupper() and len(word) > 2 and '_' in word:
                kind = 'constant'
            if kind:
                spans.append((found.start(), found.end(), kind))
            i = found.end()
            continue
        if ch == '@' and language in ('python', 'javascript'):
            found = WORD.match(line, i + 1)
            if found:
                spans.append((i, found.end(), 'meta'))
                i = found.end()
                continue
        i += 1
    return spans, state


# NvChad base46 themes (the editor's own colour schemes, taken from base46), keyed by the nvim name
# each Wysun theme variant declares in wysun_theme.json (external.nvim).
# theme-exception-begin: esquemas base46 de NvChad (sintaxis de otro programa, fiel al editor del usuario)
NVIM_SCHEMES = {'github_dark': {'base00': '#24292E',
                 'base03': '#42474c',
                 'base05': '#c9d1d9',
                 'base08': '#B392E9',
                 'base09': '#ffab70',
                 'base0A': '#ffdf5d',
                 'base0B': '#a5d6ff',
                 'base0C': '#83caff',
                 'base0D': '#6AB1F0',
                 'base0E': '#ff7f8d',
                 'comment': '#6a6f74',
                 'gutter': '#4c5156'},
 'tokyonight': {'base00': '#1a1b26',
                'base03': '#444b6a',
                'base05': '#a9b1d6',
                'base08': '#73daca',
                'base09': '#ff9e64',
                'base0A': '#0db9d7',
                'base0B': '#9ece6a',
                'base0C': '#b4f9f8',
                'base0D': '#2ac3de',
                'base0E': '#bb9af7',
                'comment': '#545c7e',
                'gutter': '#40486a'},
 'nord': {'base00': '#2E3440',
          'base03': '#4C566A',
          'base05': '#E5E9F0',
          'base08': '#88C0D0',
          'base09': '#81A1C1',
          'base0A': '#88C0D0',
          'base0B': '#A3BE8C',
          'base0C': '#81A1C1',
          'base0D': '#81A1C1',
          'base0E': '#81A1C1',
          'comment': '#646a76',
          'gutter': '#4b515d'},
 'onedark': {'base00': '#1e222a',
             'base03': '#545862',
             'base05': '#abb2bf',
             'base08': '#e06c75',
             'base09': '#d19a66',
             'base0A': '#e5c07b',
             'base0B': '#98c379',
             'base0C': '#56b6c2',
             'base0D': '#61afef',
             'base0E': '#c678dd',
             'comment': '#6f737b',
             'gutter': '#42464e'},
 'one_light': {'base00': '#fafafa',
               'base03': '#dfdfe0',
               'base05': '#383a42',
               'base08': '#d84a3d',
               'base09': '#d75f00',
               'base0A': '#c18401',
               'base0B': '#50a14f',
               'base0C': '#0070a8',
               'base0D': '#4078f2',
               'base0E': '#a626a4',
               'comment': '#a2a2a3',
               'gutter': '#b7b7b8'}}
# theme-exception-end


def scheme():
    """Base46 scheme for the active theme variant, or None when the variant names an unknown one."""
    return NVIM_SCHEMES.get(tokens().get('external', {}).get('nvim', ''))


def palette():
    """Kind -> (QColor, bold, italic) for the active theme."""
    values = tokens()
    nvim = scheme()
    if nvim:
        def hue(key, bold=False, italic=False):
            return (QColor(nvim[key]), bold, italic)
        return {'keyword': hue('base0E'), 'string': hue('base0B'), 'number': hue('base09'), 'comment': hue('comment', False, True),
                'function': hue('base0D'), 'type': hue('base0A'), 'constant': hue('base09'), 'key': hue('base0D'),
                'meta': hue('base0C', False, True)}
    ansi = values.get('external', {}).get('palette') or []

    def pick(index, fallback):
        return QColor(ansi[index][:7]) if len(ansi) > index else color(fallback)
    return {
        'keyword': (pick(5, 'cat_purple'), True, False),
        'string': (pick(2, 'cat_green'), False, False),
        'number': (pick(3, 'cat_yellow'), False, False),
        'comment': (color('muted'), False, True),
        'function': (pick(4, 'cat_blue'), False, False),
        'type': (pick(6, 'cat_cyan'), False, False),
        'constant': (pick(1, 'cat_rose'), False, False),
        'key': (pick(4, 'cat_blue'), False, False),
        'meta': (pick(6, 'cat_cyan'), False, True),
    }


def highlight_html(code, language):
    """HTML with inline colours for ``code`` (no surrounding element)."""
    colours = palette()
    out, state = [], None
    for line in code.split('\n'):
        spans, state = tokenize(line, language, state)
        cursor, parts = 0, []
        for start, end, kind in sorted(spans):
            if start < cursor:
                continue
            parts.append(escape(line[cursor:start]))
            ink, bold, italic = colours[kind]
            style = f'color:{ink.name()};' + ('font-weight:600;' if bold else '') + ('font-style:italic;' if italic else '')
            parts.append(f'<span style="{style}">{escape(line[start:end])}</span>')
            cursor = end
        parts.append(escape(line[cursor:]))
        out.append(''.join(parts))
    return '<br>'.join(out).replace('  ', '&nbsp; ').replace('\t', '&nbsp;' * 4)


class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, document, language):
        self._states, self._ids = {}, {}
        super().__init__(document)
        self.language = language
        self.refresh_theme()

    def refresh_theme(self):
        self.formats = {}
        for kind, (ink, bold, italic) in palette().items():
            fmt = QTextCharFormat()
            fmt.setForeground(ink)
            if bold:
                fmt.setFontWeight(QFont.DemiBold)
            fmt.setFontItalic(italic)
            self.formats[kind] = fmt
        self.rehighlight()

    def highlightBlock(self, text):
        previous = self.previousBlockState()
        state = self._states.get(previous) if previous > 0 else None
        spans, new = tokenize(text, self.language, state)
        for start, end, kind in spans:
            self.setFormat(start, end - start, self.formats[kind])
        if new:
            self._states.setdefault(self._ids.setdefault(new, len(self._ids) + 1), new)
            self.setCurrentBlockState(self._ids[new])
        else:
            self.setCurrentBlockState(0)
