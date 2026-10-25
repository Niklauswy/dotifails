"""Syntax-highlighted code previews painted with the user's Neovim (NvChad/base46) colours.

The colours come from Neovim itself: a headless Neovim loads NvChad's compiled base46 highlights (what the editor
really shows, which can differ from the `theme` written in chadrc.lua) and reports the treesitter groups; the
answer is cached until those files change. Pygments tokens are then mapped onto the same groups. Without
Neovim or that cache, ~/.config/nvim/lua/chadrc.lua and the base46 theme file are scanned for hex colours
instead (nothing executes Lua then). Without an NvChad setup `highlight` returns None and the launcher falls
back to its own colours.
"""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

HOME = Path.home()
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME') or HOME / '.config') / 'nvim/lua/chadrc.lua'
DATA = Path(os.environ.get('XDG_DATA_HOME') or HOME / '.local/share') / 'nvim/lazy'
BASE46_CACHE = Path(os.environ.get('XDG_DATA_HOME') or HOME / '.local/share') / 'nvim/base46'
CACHE = Path(os.environ.get('XDG_CACHE_HOME') or HOME / '.cache') / 'wysun/nvim-colours.json'
# Treesitter groups the preview uses, read from the running theme.
GROUPS = ('Normal', 'LineNr', '@comment', '@string', '@string.escape', '@string.regexp', '@number', '@boolean',
          '@constant', '@type', '@module', '@keyword', '@keyword.function', '@function', '@function.builtin',
          '@property', '@variable', '@variable.member', '@variable.builtin', '@tag', '@tag.attribute',
          '@operator', '@punctuation.delimiter', '@punctuation.bracket')
BACKUP_SUFFIX = re.compile(r'\.(?:bak|backup|bkp|backed|orig|old|save|saved|swp|tmp|new|rej|dist|disabled|(?:bak|backup|old|orig)[-_.].*|\d+)$|~$', re.I)
HEX = re.compile(r'(\w+)\s*=\s*"(#[0-9a-fA-F]{6})"')


def block(text, name):
    """Body of the first `name = { ... }` table in a Lua source (balanced braces), or ''."""
    found = re.search(rf'\b{re.escape(name)}\s*=\s*\{{', text)
    if not found:
        return ''
    depth, start = 1, found.end()
    for i in range(start, len(text)):
        depth += {'{': 1, '}': -1}.get(text[i], 0)
        if not depth:
            return text[start:i]
    return ''


def palette():
    """{'bg', 'fg', 'comment', 'lineNr', 'base00'..'base0F'} for the configured theme, or None."""
    try:
        config = CONFIG.read_text()
        theme = re.search(r'\btheme\s*=\s*"([^"]+)"', config)[1]
        source = (DATA / 'base46/lua/base46/themes' / f'{theme}.lua').read_text()
    except (OSError, TypeError):
        return None
    colours = dict(HEX.findall(block(source, 'base_16')))
    changed = block(block(block(config, 'changed_themes'), theme), 'base_16')
    colours.update(HEX.findall(changed))
    if len(colours) < 16:
        return None
    override = block(config, 'hl_override')
    comment = re.search(r'\bComment\s*=\s*\{\s*fg\s*=\s*"(#[0-9a-fA-F]{6})"', override)
    line_nr = re.search(r'\bLineNr\s*=\s*\{\s*fg\s*=\s*"(#[0-9a-fA-F]{6})"', override)
    colours.update(transparent=bool(re.search(r'\btransparency\s*=\s*true', config)), bg=colours['base00'], fg=colours['base05'], comment=comment[1] if comment else colours['base03'],
                   lineNr=line_nr[1] if line_nr else colours['base03'])
    return colours


def nvim_colours():
    """{group: {'fg', 'bg', 'italic'}} as the user's Neovim draws them, or None. Cached by the base46 files."""
    files = [BASE46_CACHE / f for f in ('defaults', 'syntax', 'treesitter')]
    nvim = shutil.which('nvim')
    if not nvim or not all(f.is_file() for f in files):
        return None
    key = hashlib.sha1('|'.join(f'{f}:{f.stat().st_mtime_ns}' for f in files).encode()).hexdigest()
    try:
        cached = json.loads(CACHE.read_text())
        if cached.get('key') == key:
            return cached['groups']
    except (OSError, ValueError, AttributeError):
        pass
    lua = ('local out = {} for _, f in ipairs({"defaults", "syntax", "treesitter"}) do pcall(dofile, %s .. f) end '
           'for _, g in ipairs(vim.json.decode(%s)) do local h = vim.api.nvim_get_hl(0, {name = g, link = false}) '
           'out[g] = {fg = h.fg and string.format("#%%06x", h.fg) or vim.NIL, bg = h.bg and string.format("#%%06x", h.bg) or vim.NIL, italic = h.italic or false} end '
           'io.stdout:write(vim.json.encode(out)) vim.cmd("qa!")') % (json.dumps(str(BASE46_CACHE) + '/'), json.dumps(json.dumps(GROUPS)))
    try:
        result = subprocess.run([nvim, '--headless', '-c', 'lua ' + lua], capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
        groups = json.loads(result.stdout[result.stdout.index('{'):])
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if not (groups.get('Normal') or {}).get('fg'):
        return None
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps({'key': key, 'groups': groups}))
    except OSError:
        pass
    return groups


def group_colour(groups, *names):
    """(colour, italic) of the first of `names` the theme defines, else the normal text colour."""
    for name in names:
        h = groups.get(name) or {}
        if h.get('fg'):
            return h['fg'], bool(h.get('italic'))
    return groups['Normal']['fg'], False


def nvim_token_colour(token, groups, lexer):
    """(colour, italic) for a Pygments token, using the groups treesitter would paint it with in Neovim."""
    from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String, Literal
    if token in Comment:
        return group_colour(groups, '@comment')
    if token in String.Escape:
        return group_colour(groups, '@string.escape', '@string')
    if token in String.Regex:
        return group_colour(groups, '@string.regexp', '@string')
    if token in String:
        return group_colour(groups, '@string')
    if token in Number:
        return group_colour(groups, '@number')
    if token in Keyword.Constant:
        return group_colour(groups, '@boolean', '@constant')
    if token in Literal or token in Name.Constant:
        return group_colour(groups, '@constant')
    if token in Keyword.Type or token in Name.Class or token in Name.Exception:
        return group_colour(groups, '@type')
    if token in Name.Namespace:
        return group_colour(groups, '@module', '@type')
    if token in Keyword:
        return group_colour(groups, '@keyword')
    if token in Name.Function or token in Name.Decorator:
        return group_colour(groups, '@function')
    if token in Name.Builtin.Pseudo:
        return group_colour(groups, '@variable.builtin', '@variable')
    if token in Name.Builtin:
        return group_colour(groups, '@function.builtin', '@function')
    if token in Name.Tag:
        # Keys of JSON-like data are tags to Pygments and properties to treesitter.
        return group_colour(groups, '@property') if lexer in ('JSON', 'JSONBareObject', 'JSON5', 'YAML', 'TOML') else group_colour(groups, '@tag')
    if token in Name.Attribute:
        return group_colour(groups, '@tag.attribute', '@property')
    if token in Name.Property or token in Name.Variable.Instance:
        return group_colour(groups, '@variable.member', '@property')
    if token in Operator:
        return group_colour(groups, '@operator')
    if token in Punctuation:
        return group_colour(groups, '@punctuation.delimiter')
    return group_colour(groups, '@variable')


def token_colour(token, p):
    """(colour, italic) for a Pygments token, following base46's treesitter groups."""
    from pygments.token import Comment, Keyword, Name, Number, Operator, String, Literal
    if token in Comment:
        return p['comment'], True
    if token in String.Escape or token in String.Regex:
        return p['base0C'], False
    if token in String:
        return p['base0B'], False
    if token in Number or token in Literal or token in Name.Constant:
        return p['base09'], False
    if token in Keyword.Type or token in Name.Class or token in Name.Exception or token in Name.Namespace:
        return p['base0A'], False
    if token in Keyword:
        return p['base0E'], False
    if token in Name.Function or token in Name.Decorator:
        return p['base0D'], False
    if token in Name.Builtin or token in Name.Attribute:
        return p['base0C'], False
    if token in Name.Tag:
        return p['base08'], False
    if token in Operator:
        return p['base04'], False
    return p['fg'], False


def highlight(path, text):
    """{'html', 'bg', 'fg', 'lineNr', 'transparent', 'lexer'} for `text` shown as `path`, or None without theme/Pygments."""
    groups = nvim_colours()
    p = palette() if groups is None else None
    if groups is None and p is None:
        return None
    try:
        from pygments.lexers import get_lexer_for_filename, TextLexer
        from pygments.util import ClassNotFound
    except ImportError:
        return None
    try:
        name = Path(path).name
        while BACKUP_SUFFIX.search(name) and len(name) > 1:
            name = BACKUP_SUFFIX.sub('', name, count=1)  # a backup is highlighted as what it backs up
        lexer = get_lexer_for_filename(name, text)
    except ClassNotFound:
        lexer = TextLexer()
    runs = []
    for token, value in lexer.get_tokens(text.expandtabs(4)):
        if value.strip() or not runs:
            colour, italic = nvim_token_colour(token, groups, lexer.name) if groups else token_colour(token, p)
        else:
            colour, italic = None, False  # whitespace takes whatever colour comes before it
        runs.append((colour, italic, value))
    if groups:
        normal = groups['Normal']
        transparent = bool(re.search(r'\btransparency\s*=\s*true', CONFIG.read_text())) if CONFIG.is_file() else not normal.get('bg')
        p = dict(fg=normal['fg'], bg=normal.get('bg') or '#000000', lineNr=group_colour(groups, 'LineNr')[0], transparent=transparent)  # theme-exception: fallback for an absent external Neovim background
    return dict(html=markup(runs, p['fg']), bg=p['bg'], fg=p['fg'], lineNr=p['lineNr'], transparent=p['transparent'], lexer=lexer.name)


def markup(runs, fg):
    """Qt StyledText for [(colour or None, italic, text)]: the same picture as RichText, laid out about seven times
    faster. Qt makes every span a fragment, so consecutive runs of one style merge and uncoloured text joins the
    run before it; text in the normal colour needs no tag at all."""
    merged = []
    for colour, italic, value in runs:
        style = (colour or fg, italic) if colour or not merged else merged[-1][0]
        if merged and merged[-1][0] == style:
            merged[-1][1].append(value)
        else:
            merged.append((style, [value]))
    out = []
    for (colour, italic), parts in merged:
        value = html.escape(''.join(parts), quote=False).replace(' ', '&nbsp;').replace('\n', '<br>')
        if italic:
            value = f'<i>{value}</i>'
        out.append(value if colour == fg else f'<font color="{colour}">{value}</font>')
    text = ''.join(out)
    while text.endswith('<br>'):
        text = text[:-4]
    return text


SCRIPT = Path(__file__).resolve().parent / 'nvim_highlight.lua'


def render(path, max_lines):
    """The first lines of `path` coloured by Neovim itself (treesitter, or Vim syntax where it has no parser):
    {'html', 'bg', 'fg', 'lineNr', 'transparent', 'lexer'}, or None without Neovim or NvChad's highlights."""
    nvim = shutil.which('nvim')
    if not nvim or not SCRIPT.is_file() or not (BASE46_CACHE / 'defaults').is_file():
        return None
    try:
        result = subprocess.run([nvim, '--clean', '--headless', '-l', str(SCRIPT), str(path), str(max_lines), str(BASE46_CACHE), str(DATA / 'nvim-treesitter')],
                                capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
        data = json.loads(result.stdout[result.stdout.index('{'):])
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if data.get('error') or not data.get('normal'):
        return None
    runs = []
    for row, line in enumerate(data['lines']):
        if row:
            runs.append((None, False, '\n'))
        col = 0
        for value, colour, italic in line:
            if '\t' in value:  # tabs as the preview's text shows them, from the column they start at
                value = (' ' * col + value).expandtabs(4)[col:]
            col += len(value)
            # Uncoloured text is Neovim's normal text; only blank stretches may join the run before them.
            runs.append((colour or (data['normal'] if value.strip() else None), bool(italic), value))
    transparent = bool(re.search(r'\btransparency\s*=\s*true', CONFIG.read_text())) if CONFIG.is_file() else not data.get('bg')
    return dict(html=markup(runs, data['normal']), bg=data.get('bg') or '#000000', fg=data['normal'], lineNr=data.get('lineNr') or data['normal'],  # theme-exception: fallback for an absent external Neovim background
                transparent=transparent, lexer=data.get('lang', ''))


def stamp():
    """Changes whenever the colours `highlight` would use change: chadrc, NvChad's compiled highlights and the base46 theme file."""
    parts = []
    for f in ('defaults', 'syntax', 'treesitter'):
        try:
            parts.append(str((BASE46_CACHE / f).stat().st_mtime_ns))
        except OSError:
            parts.append('-')
    try:
        st = CONFIG.stat()
        parts.append(f'{st.st_mtime_ns}:{st.st_size}')
        theme = re.search(r'\btheme\s*=\s*"([^"]+)"', CONFIG.read_text())
        if theme:
            parts.append(str((DATA / 'base46/lua/base46/themes' / f'{theme[1]}.lua').stat().st_mtime_ns))
    except OSError:
        parts.append('none')
    return '|'.join(parts)
