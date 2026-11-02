"""The launcher's file search for Wysun Files, without Qt: the same index (``launcher-files.idx``: ``d<path>`` /
``f<path>`` lines relative to the home folder) and the same scoring as the shell's ``FileSearch.mjs``. Every query
token must match; each is scored against the entry's name first and then against the folders above it."""
from dataclasses import dataclass
import re
import unicodedata

HIDDEN_PENALTY, FOLDER_BONUS, DEPTH_COST = 120, 12, 0.15
_WORD_START = ' ._-'


def fold(text):
    text = text.lower()
    if text.isascii():
        return text
    return ''.join(c for c in unicodedata.normalize('NFD', text) if not unicodedata.combining(c))


@dataclass
class Index:
    paths: list
    folders: list
    folded: list
    names: list

    @property
    def size(self):
        return len(self.paths)


def parse(text):
    paths, folders, folded, names = [], [], [], []
    for line in text.split('\n'):
        if len(line) < 2:
            continue
        path = line[1:]
        low = fold(path)
        paths.append(path)
        folders.append(line[0] == 'd')
        folded.append(low)
        names.append(low[low.rfind('/') + 1:])
    return Index(paths, folders, folded, names)


def load(file):
    try:
        with open(file, encoding='utf-8', errors='surrogateescape') as handle:
            return parse(handle.read())
    except OSError:
        return parse('')


def _fuzzy(token, name):
    """Subsequence match; rewards runs and word starts. 0 when ``token`` is not a subsequence of ``name``."""
    at, previous, score = 0, -2, 120
    for char in token:
        found = name.find(char, at)
        if found < 0:
            return 0
        if found == previous + 1:
            score += 8
        else:
            score -= min(found - previous - 1, 12)
        if found == 0 or name[found - 1] in _WORD_START:
            score += 10
        previous, at = found, found + 1
    return max(score, 20)


def _token_score(token, name, path):
    if name == token:
        return 1000
    if name.startswith(token):
        return 800 - min(len(name) - len(token), 100) * 0.5
    at = name.find(token)
    if at >= 0:
        boundary = at > 0 and name[at - 1] in _WORD_START
        return (650 if boundary else 420) - min(at, 100) * 0.5
    if len(token) >= 2 and len(name) <= 64:
        score = _fuzzy(token, name)
        if score:
            return score
    in_path = path.find(token)
    if 0 <= in_path < len(path) - len(name):
        return 160 - min(in_path, 100) * 0.3
    return 0


def search(index, query, limit=150):
    """``[(path relative to home, is folder)]``, best first. Hidden entries rank below visible ones unless the query
    itself asks for a dot-name."""
    tokens = [t for t in re.split(r'\s+', fold(query).strip()) if t]
    if not tokens:
        return []
    wants_hidden = any(t[0] == '.' for t in tokens)
    hits = []
    for i, path in enumerate(index.folded):
        name, total = index.names[i], 0
        for token in tokens:
            score = _token_score(token, name, path)
            if not score:
                total = 0
                break
            total += score
        if not total:
            continue
        hidden = not wants_hidden and (path[0] == '.' or '/.' in path)
        hits.append((-(total - len(path) * DEPTH_COST + (FOLDER_BONUS if index.folders[i] else 0)
                       - (HIDDEN_PENALTY if hidden else 0)), i))
    hits.sort()
    return [(index.paths[i], index.folders[i]) for _score, i in hits[:limit]]
