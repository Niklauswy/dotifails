"""Markdown (CommonMark subset) to a block tree plus inline HTML, no dependencies.

Blocks: heading, para, code, quote, list (bullets, numbers, tasks, nesting),
table, rule and standalone image. Inline: code, emphasis, strike, links and
autolinks. Styling is done by the widgets that consume the tree.
"""
from html import escape
import re

FENCE = re.compile(r'^(\s*)(`{3,}|~{3,})\s*([^\s`]*)')
HEADING = re.compile(r'^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$')
RULE = re.compile(r'^\s{0,3}([-*_])(?:\s*\1){2,}\s*$')
ITEM = re.compile(r'^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$')
TASK = re.compile(r'^\[([ xX])\]\s+(.*)$')
SEPARATOR = re.compile(r'^\s*\|?\s*:?-{1,}:?\s*(?:\|\s*:?-{1,}:?\s*)*\|?\s*$')
IMAGE_ONLY = re.compile(r'^!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)$')
CODE_SPAN = re.compile(r'(`+)(.+?)\1', re.S)
LINK = re.compile(r'\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)')
INLINE_IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)[^)]*\)')
AUTOLINK = re.compile(r'&lt;(https?://[^\s&]+)&gt;|(?<![\w"=>/])(https?://[^\s<)\]]+)')
BOLD = re.compile(r'\*\*(.+?)\*\*|__(.+?)__')
ITALIC = re.compile(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\*)|(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])')
STRIKE = re.compile(r'~~(.+?)~~')


def split_front_matter(text):
    lines = text.split('\n')
    if len(lines) > 2 and lines[0].strip() == '---':
        for number in range(1, min(len(lines), 60)):
            if lines[number].strip() in ('---', '...'):
                return '\n'.join(lines[1:number]), '\n'.join(lines[number + 1:])
    return '', text


def _starts_block(line, following=None):
    return bool(FENCE.match(line) or HEADING.match(line) or RULE.match(line) or line.lstrip().startswith('>')
                or ITEM.match(line) or (following is not None and '|' in line and SEPARATOR.match(following)))


def parse(text):
    return _blocks(text.replace('\r\n', '\n').replace('\t', '    ').split('\n'))


def _cells(row):
    row = row.strip()
    if row.startswith('|'):
        row = row[1:]
    if row.endswith('|') and not row.endswith('\\|'):
        row = row[:-1]
    return [cell.strip().replace('\\|', '|') for cell in re.split(r'(?<!\\)\|', row)]


def _blocks(lines):
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        fence = FENCE.match(line)
        if fence:
            marker, language, body = fence.group(2), fence.group(3), []
            i += 1
            while i < len(lines) and not re.match(r'^\s*' + re.escape(marker[0]) + '{%d,}\\s*$' % len(marker), lines[i]):
                body.append(lines[i][min(len(fence.group(1)), len(lines[i]) - len(lines[i].lstrip())):])
                i += 1
            out.append({'t': 'code', 'lang': language, 'text': '\n'.join(body)})
            i += 1
            continue
        heading = HEADING.match(line)
        if heading:
            out.append({'t': 'heading', 'level': len(heading.group(1)), 'text': heading.group(2)})
            i += 1
            continue
        if RULE.match(line):
            out.append({'t': 'rule'})
            i += 1
            continue
        if line.lstrip().startswith('>'):
            body = []
            while i < len(lines) and lines[i].lstrip().startswith('>'):
                body.append(re.sub(r'^\s*>\s?', '', lines[i]))
                i += 1
            out.append({'t': 'quote', 'children': _blocks(body)})
            continue
        item = ITEM.match(line)
        if item:
            i = _list(lines, i, out)
            continue
        if '|' in line and i + 1 < len(lines) and SEPARATOR.match(lines[i + 1]) and '-' in lines[i + 1]:
            head = _cells(line)
            align = []
            for cell in _cells(lines[i + 1]):
                align.append('center' if cell.startswith(':') and cell.endswith(':') else 'right' if cell.endswith(':') else 'left')
            rows, i = [], i + 2
            while i < len(lines) and lines[i].strip() and '|' in lines[i]:
                rows.append(_cells(lines[i]))
                i += 1
            out.append({'t': 'table', 'head': head, 'align': align, 'rows': rows})
            continue
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not _starts_block(lines[i], lines[i + 1] if i + 1 < len(lines) else None):
            if re.fullmatch(r'=+|-+', lines[i].strip()):
                break
            para.append(lines[i].strip())
            i += 1
        if i < len(lines) and re.fullmatch(r'\s{0,3}(=+|-+)\s*', lines[i]) and len(para) >= 1 and lines[i].strip():
            out.append({'t': 'heading', 'level': 1 if lines[i].strip()[0] == '=' else 2, 'text': ' '.join(para)})
            i += 1
            continue
        joined = '\n'.join(para)
        image = IMAGE_ONLY.match(joined)
        out.append({'t': 'image', 'alt': image.group(1), 'src': image.group(2)} if image else {'t': 'para', 'text': joined})
    return out


def _list(lines, i, out):
    first = ITEM.match(lines[i])
    base = len(first.group(1))
    ordered = first.group(2)[0].isdigit()
    start = int(re.match(r'\d+', first.group(2)).group()) if ordered else 1
    items = []
    while i < len(lines):
        match = ITEM.match(lines[i])
        if not match or len(match.group(1)) != base or match.group(2)[0].isdigit() != ordered:
            break
        width = len(match.group(1)) + len(match.group(2)) + 1
        body = [match.group(3)]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                if i + 1 < len(lines) and lines[i + 1].startswith(' ' * (base + 2)) and lines[i + 1].strip():
                    body.append('')
                    i += 1
                    continue
                break
            indent = len(nxt) - len(nxt.lstrip())
            if indent <= base and (ITEM.match(nxt) or _starts_block(nxt)):
                break
            body.append(nxt[min(width, indent):] if indent >= base + 2 else nxt.strip())
            i += 1
        task = TASK.match(body[0])
        if task:
            body[0] = task.group(2)
        items.append({'task': None if not task else task.group(1) != ' ', 'children': _blocks(body)})
        if i < len(lines) and not lines[i].strip():
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            follow = ITEM.match(lines[j]) if j < len(lines) else None
            if follow and len(follow.group(1)) == base and follow.group(2)[0].isdigit() == ordered:
                i = j
                continue
            break
    out.append({'t': 'list', 'ordered': ordered, 'start': start, 'items': items})
    return i


def inline(text, ink):
    """HTML of one paragraph. ``ink`` supplies ``link``, ``code_bg``, ``code_fg``, ``mono`` and ``muted``."""
    spans = []

    def keep(match):
        spans.append(match.group(2).strip())
        return f'\0{len(spans) - 1}\0'
    text = CODE_SPAN.sub(keep, text)
    text = escape(text, quote=True)
    hard = re.compile(r'(?: {2,}|\\)\n')
    text = hard.sub('<br>', text).replace('\n', ' ')
    text = INLINE_IMAGE.sub(lambda m: f'<span style="color:{ink["muted"]};">[{m.group(1) or "imagen"}]</span>', text)
    text = LINK.sub(lambda m: f'<a href="{m.group(2)}" style="color:{ink["link"]};text-decoration:none;">{m.group(1)}</a>', text)
    text = AUTOLINK.sub(lambda m: f'<a href="{m.group(1) or m.group(2)}" style="color:{ink["link"]};text-decoration:none;">{m.group(1) or m.group(2)}</a>', text)
    text = BOLD.sub(lambda m: f'<b>{m.group(1) or m.group(2)}</b>', text)
    text = ITALIC.sub(lambda m: f'<i>{m.group(1) or m.group(2)}</i>', text)
    text = STRIKE.sub(lambda m: f'<s>{m.group(1)}</s>', text)
    return re.sub(r'\0(\d+)\0', lambda m: (
        f'<span style="font-family:{ink["mono"]};background-color:{ink["code_bg"]};color:{ink["code_fg"]};">'
        f'&nbsp;{escape(spans[int(m.group(1))])}&nbsp;</span>'), text)
