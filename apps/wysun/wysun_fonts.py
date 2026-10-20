"""Registro de las fuentes empaquetadas de Wysun para las apps Qt.

Rubik es la familia de texto y Material Symbols Rounded la de iconos por
ligadura. Las fuentes viajan con la shell (``apps/shell/assets/fonts``); este
módulo las registra con ``QFontDatabase`` desde el árbol de desarrollo o desde
la shell instalada. No instala nada en el sistema, no descarga archivos y no
modifica el entorno del usuario.

La lista de iconos válidos es el mismo archivo que usa el generador del subset
(``material-symbols-glyphs.txt``), de modo que QML y Qt comparten contrato.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QFontDatabase

TEXT_FILE = "Rubik-Variable.ttf"
TEXT_FAMILY = "Rubik"
ICON_FILE = "MaterialSymbolsRounded.ttf"
ICON_FAMILY = "Material Symbols Rounded"
GLYPH_FILE = "material-symbols-glyphs.txt"
#: Marca neutra que se dibuja con cualquier fuente si no hay icono disponible.
FALLBACK_ICON = "\u25cb"  # ○
TEXT_FALLBACKS = ("Inter", "Sans Serif")

_REPO_FONTS = Path(__file__).resolve().parent / "assets/fonts"


def glyph_names(path: Path | None = None) -> tuple[str, ...]:
    """Nombres de Material Symbols aprobados, uno por línea en el contrato."""
    return _glyph_names(str(path or _REPO_FONTS / GLYPH_FILE))


@lru_cache(maxsize=4)
def _glyph_names(source: str) -> tuple[str, ...]:
    path = Path(source)
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError(f"Duplicated Material Symbols names in {path}")
    if not names:
        raise ValueError(f"No Material Symbols names in {path}")
    return tuple(names)


def candidate_dirs() -> tuple[Path, ...]:
    """Directorios de fuentes, en orden de preferencia, sin duplicados.

    ``WYSUN_FONTS_DIR`` permite a un release o a una prueba apuntar a su propia
    copia. Después se busca el árbol de desarrollo y la shell instalada.
    """
    dirs: list[Path] = []
    override = os.environ.get("WYSUN_FONTS_DIR")
    if override:
        dirs.append(Path(override).expanduser())
    dirs.append(_REPO_FONTS)
    dirs.append(Path(__file__).resolve().parent / "assets/fonts")
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    dirs.extend((
        data_home / "wysun/quickshell/assets/fonts",
        Path.home() / ".local/share/wysun/quickshell/assets/fonts",
        Path.home() / ".local/share/orbit/app/assets/fonts",
    ))
    unique: list[Path] = []
    for directory in dirs:
        if directory not in unique:
            unique.append(directory)
    return tuple(unique)


def _locate(filename: str, roots: tuple[Path, ...]) -> Path | None:
    for root in roots:
        candidate = root / filename
        if candidate.is_file():
            return candidate
    return None


class Fonts:
    """Fuentes de Wysun registradas para una app Qt.

    ``register()`` es idempotente por instancia. Las propiedades indican qué se
    encontró realmente; ``family()``, ``icon_family()`` e ``icon()`` degradan a
    valores seguros cuando falta un archivo.
    """

    def __init__(self, fonts_dir: Path | str | None = None):
        self._explicit = Path(fonts_dir).expanduser() if fonts_dir else None
        self.text_path: Path | None = None
        self.icon_path: Path | None = None
        self.glyph_path: Path | None = None
        self._text_family = ""
        self._icon_family = ""
        self._names: tuple[str, ...] = ()
        self._name_set: frozenset[str] = frozenset()
        self._registered = False

    @property
    def roots(self) -> tuple[Path, ...]:
        return (self._explicit,) if self._explicit else candidate_dirs()

    @property
    def text_available(self) -> bool:
        return bool(self._text_family)

    @property
    def icons_available(self) -> bool:
        return bool(self._icon_family)

    def register(self) -> "Fonts":
        """Carga las fuentes encontradas. Seguro si se llama más de una vez."""
        if self._registered:
            return self
        self._registered = True
        roots = self.roots
        self.text_path = _locate(TEXT_FILE, roots)
        self.icon_path = _locate(ICON_FILE, roots)
        self.glyph_path = _locate(GLYPH_FILE, roots) or (_REPO_FONTS / GLYPH_FILE)
        self._names = glyph_names(self.glyph_path)
        self._name_set = frozenset(self._names)
        if self.text_path:
            self._text_family = self._add(self.text_path, TEXT_FAMILY)
        if self.icon_path:
            self._icon_family = self._add(self.icon_path, ICON_FAMILY)
        return self

    @staticmethod
    def _add(path: Path, expected: str) -> str:
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            return ""
        families = QFontDatabase.applicationFontFamilies(font_id)
        if expected in families:
            return expected
        return families[0] if families else ""

    def family(self) -> str:
        """Familia de texto: Rubik si está disponible; si no, una del sistema."""
        if self.text_available:
            return self._text_family
        installed = set(QFontDatabase.families())
        return next((name for name in TEXT_FALLBACKS if name in installed), TEXT_FALLBACKS[-1])

    def icon_family(self) -> str:
        """Familia para ``icon()``; la de texto sirve para el respaldo."""
        return self._icon_family or self.family()

    def icon(self, name: str, fallback: str = FALLBACK_ICON) -> str:
        """Texto de ligadura del icono ``name``, o ``fallback`` si no procede.

        Un nombre fuera del contrato o una fuente ausente nunca devuelven el
        nombre en crudo: así una ligadura sin resolver jamás aparece como texto.
        """
        if not self.icons_available or name not in self._name_set:
            return fallback
        return name

    def names(self) -> tuple[str, ...]:
        return self._names


_default: Fonts | None = None


def register(fonts_dir: Path | str | None = None) -> Fonts:
    """Registra las fuentes una sola vez por proceso y devuelve el registro."""
    global _default
    if fonts_dir is not None:
        return Fonts(fonts_dir).register()
    if _default is None:
        _default = Fonts().register()
    return _default


def family() -> str:
    return register().family()


def icon_family() -> str:
    return register().icon_family()


def icon(name: str, fallback: str = FALLBACK_ICON) -> str:
    return register().icon(name, fallback)


def names() -> tuple[str, ...]:
    return register().names()
