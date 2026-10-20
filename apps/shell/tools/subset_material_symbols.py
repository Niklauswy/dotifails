#!/usr/bin/env python3
"""Create Wysun's small Material Symbols Rounded runtime subset.

Requires fontTools 4.67.0 or newer as a developer-only tool. It does not run at
runtime and does not modify the supplied upstream source font.

The icons come from ``apps/shell/assets/fonts/material-symbols-glyphs.txt``;
that file, not this script, is the single list of icon names shared with
``apps/wysun/wysun_fonts.py``.

Usage:
  python3 apps/shell/tools/subset_material_symbols.py FULL_FONT.ttf OUTPUT.ttf
"""
from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont


GLYPH_FILE = Path(__file__).resolve().parent.parent / "assets/fonts/material-symbols-glyphs.txt"


def load_glyphs(path: Path = GLYPH_FILE) -> frozenset[str]:
    """Icon names requested by the shell and Qt apps, one per line.

    The list is the single source of truth for both this subset and
    ``apps/wysun/wysun_fonts.py``. Blank lines and ``#`` comments are ignored.
    """
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        if not name.replace("_", "").isalnum():
            raise ValueError(f"Invalid Material Symbols name in {path}: {name!r}")
        names.append(name)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError("Duplicated Material Symbols names: " + ", ".join(duplicates))
    if not names:
        raise ValueError(f"No Material Symbols names in {path}")
    return frozenset(names)


def _subtables(lookup):
    for table in lookup.SubTable:
        lookup_type = lookup.LookupType
        if lookup_type == 7:  # ExtensionSubst can wrap the ligature lookup.
            lookup_type = table.ExtensionLookupType
            table = table.ExtSubTable
        yield lookup_type, table


def _ligature_map(font, used_glyphs):
    glyph_to_char = {}
    # The same base glyph is mapped from both cases (A and a). Iterate in
    # codepoint order and keep the last mapping so ligature text stays lowercase.
    for codepoint, glyph in sorted(font.getBestCmap().items()):
        glyph_to_char[glyph] = chr(codepoint)
    ligatures = {}
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for lookup_type, table in _subtables(lookup):
            if lookup_type != 4:  # LigatureSubst
                continue
            for first, rows in table.ligatures.items():
                for ligature in rows:
                    if ligature.LigGlyph not in used_glyphs:
                        continue
                    sequence = [first, *ligature.Component]
                    text = "".join(glyph_to_char[glyph] for glyph in sequence)
                    ligatures[text] = ligature.LigGlyph
    return ligatures


def _axes(font):
    return tuple((axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue)
                 for axis in font["fvar"].axes)


def _keep_used_ligatures(font, used_glyphs):
    kept = set()
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for lookup_type, table in _subtables(lookup):
            if lookup_type != 4:
                continue
            for first, ligatures in list(table.ligatures.items()):
                selected = [ligature for ligature in ligatures if ligature.LigGlyph in used_glyphs]
                kept.update(ligature.LigGlyph for ligature in selected)
                if selected:
                    table.ligatures[first] = selected
                else:
                    del table.ligatures[first]
    missing = used_glyphs - kept
    if missing:
        raise ValueError("Upstream font is missing used ligatures: " + ", ".join(sorted(missing)))


def build_subset(source: Path, output: Path, glyph_file: Path = GLYPH_FILE) -> None:
    used_glyphs = load_glyphs(glyph_file)
    used_text = " ".join(sorted(used_glyphs))
    if source.resolve() == output.resolve():
        raise ValueError("Input and output font paths must differ")

    font = TTFont(source)
    axes = _axes(font)
    source_ligatures = _ligature_map(font, used_glyphs)
    if any(source_ligatures.get(name) != name for name in used_glyphs):
        raise ValueError("Upstream font ligature map changed for a used Wysun icon")
    _keep_used_ligatures(font, used_glyphs)

    # Limit closure to the Wysun ligatures above while keeping the OpenType
    # substitution tables, names and variable axes needed by Qt's text shaper.
    options = Options()
    options.layout_features = ["*"]
    options.glyph_names = True
    options.recommended_glyphs = True
    subsetter = Subsetter(options=options)
    subsetter.populate(text=used_text)
    subsetter.subset(font)

    output_ligatures = _ligature_map(font, used_glyphs)
    if any(output_ligatures.get(name) != name for name in used_glyphs):
        raise ValueError("Subset is missing a Wysun icon ligature")
    outputs = set(output_ligatures.values())
    if outputs != set(used_glyphs):
        raise ValueError("Subset has unexpected icon outputs: " + ", ".join(sorted(outputs)))
    if _axes(font) != axes:
        raise ValueError("Subset did not preserve all variable font axes")
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Full upstream Material Symbols Rounded TTF")
    parser.add_argument("output", type=Path, help="Subset TTF output path")
    parser.add_argument("--glyphs", type=Path, default=GLYPH_FILE,
                        help=f"Icon-name list (default: {GLYPH_FILE})")
    args = parser.parse_args()
    build_subset(args.source, args.output, args.glyphs)
    print(f"Wrote {args.output} ({args.output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
