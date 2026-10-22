"""File kinds: Material symbol, theme category tone and Spanish label per extension."""
from pathlib import Path

from file_media import AUDIO, CODE, IMAGES, VIDEOS

ARCHIVES = {'.zip', '.tar', '.gz', '.bz2', '.xz', '.zst', '.7z', '.rar', '.tgz', '.deb', '.rpm', '.appimage'}
SHEETS = {'.csv', '.tsv', '.xls', '.xlsx', '.ods'}
SLIDES = {'.ppt', '.pptx', '.odp'}
TEXTS = {'.doc', '.docx', '.odt', '.rtf'}
NOTES = {'.md', '.markdown', '.txt', '.rst', '.log', '.tex', '.srt', '.vtt'}
SCRIPTS = {'.sh', '.bash', '.zsh', '.fish'}
FONTS = {'.ttf', '.otf', '.woff', '.woff2'}
DISKS = {'.iso', '.img'}
MARKDOWN = {'.md', '.markdown'}
PLAIN = NOTES | {'.csv', '.tsv', '.json', '.yaml', '.yml', '.toml', '.ini', '.conf', '.cfg', '.env', '.desktop', '.service'}

# kind -> (Material symbol, colour token, label)
FOLDER = ('folder', 'accent', 'Carpeta')
GENERIC = ('draft', 'cat_slate', 'Archivo')


def describe(path, is_dir=None):
    """(symbol, tone, label) of a path; never touches the disk when ``is_dir`` is given."""
    if is_dir is None:
        is_dir = Path(path).is_dir()
    if is_dir:
        return FOLDER
    suffix = Path(path).suffix.lower()
    if suffix in IMAGES:
        return 'image', 'cat_purple', 'Imagen'
    if suffix in VIDEOS:
        return 'movie', 'cat_rose', 'Vídeo'
    if suffix in AUDIO:
        return 'music_note', 'cat_orange', 'Audio'
    if suffix == '.pdf':
        return 'picture_as_pdf', 'cat_rose', 'Documento PDF'
    if suffix in MARKDOWN:
        return 'article', 'cat_blue', 'Markdown'
    if suffix in SCRIPTS:
        return 'terminal', 'cat_green', 'Script'
    if suffix in CODE:
        return 'code', 'cat_cyan', 'Código'
    if suffix in SHEETS:
        return 'table_chart', 'cat_green', 'Hoja de cálculo'
    if suffix in SLIDES:
        return 'slideshow', 'cat_orange', 'Presentación'
    if suffix in TEXTS or suffix in NOTES:
        return 'description', 'cat_blue', 'Documento'
    if suffix in ARCHIVES:
        return 'folder_zip', 'cat_yellow', 'Archivo comprimido'
    if suffix in FONTS:
        return 'font_download', 'cat_lavender', 'Tipografía'
    if suffix in DISKS:
        return 'album', 'cat_indigo', 'Imagen de disco'
    return GENERIC


def preview_kind(path):
    """How the inspector renders a file: image/video/audio/markdown/code/text/pdf or ''."""
    suffix = Path(path).suffix.lower()
    if suffix in IMAGES:
        return 'image'
    if suffix in VIDEOS:
        return 'video'
    if suffix in AUDIO:
        return 'audio'
    if suffix == '.pdf':
        return 'pdf'
    if suffix in MARKDOWN:
        return 'markdown'
    if suffix in CODE or suffix in SCRIPTS:
        return 'code'
    if suffix in PLAIN:
        return 'text'
    return ''
