#!/usr/bin/env python3
"""Create Wysun's small Material Symbols Rounded runtime subset.

Requires fontTools 4.67.0 or newer as a developer-only tool. It does not run at
runtime and does not modify the supplied upstream source font.

Usage:
  python3 apps/shell/tools/subset_material_symbols.py FULL_FONT.ttf OUTPUT.ttf
"""
from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont


USED_GLYPHS = frozenset({
    "dashboard",
    "volume_off",
    "volume_mute",
    "volume_up",
    "wifi",
    "battery_alert",
    "battery_full",
    "power_settings_new",
    "close",
})
USED_TEXT = " ".join(sorted(USED_GLYPHS))


def _subtables(lookup):
    for table in lookup.SubTable:
        lookup_type = lookup.LookupType
        if lookup_type == 7:  # ExtensionSubst can wrap the ligature lookup.
            lookup_type = table.ExtensionLookupType
            table = table.ExtSubTable
        yield lookup_type, table


def _ligature_map(font):
    glyph_to_char = {}
    for codepoint, glyph in font.getBestCmap().items():
        glyph_to_char.setdefault(glyph, chr(codepoint))
    ligatures = {}
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for lookup_type, table in _subtables(lookup):
            if lookup_type != 4:  # LigatureSubst
                continue
            for first, rows in table.ligatures.items():
                for ligature in rows:
                    if ligature.LigGlyph not in USED_GLYPHS:
                        continue
                    sequence = [first, *ligature.Component]
                    text = "".join(glyph_to_char[glyph] for glyph in sequence)
                    ligatures[text] = ligature.LigGlyph
    return ligatures


def _axes(font):
    return tuple((axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue)
                 for axis in font["fvar"].axes)


def _keep_used_ligatures(font):
    kept = set()
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for lookup_type, table in _subtables(lookup):
            if lookup_type != 4:
                continue
            for first, ligatures in list(table.ligatures.items()):
                selected = [ligature for ligature in ligatures if ligature.LigGlyph in USED_GLYPHS]
                kept.update(ligature.LigGlyph for ligature in selected)
                if selected:
                    table.ligatures[first] = selected
                else:
                    del table.ligatures[first]
    missing = USED_GLYPHS - kept
    if missing:
        raise ValueError("Upstream font is missing used ligatures: " + ", ".join(sorted(missing)))


def build_subset(source: Path, output: Path) -> None:
    if source.resolve() == output.resolve():
        raise ValueError("Input and output font paths must differ")

    font = TTFont(source)
    axes = _axes(font)
    source_ligatures = _ligature_map(font)
    if any(source_ligatures.get(name) != name for name in USED_GLYPHS):
        raise ValueError("Upstream font ligature map changed for a used Wysun icon")
    _keep_used_ligatures(font)

    # Limit closure to the Wysun ligatures above while keeping the OpenType
    # substitution tables, names and variable axes needed by Qt's text shaper.
    options = Options()
    options.layout_features = ["*"]
    options.glyph_names = True
    options.recommended_glyphs = True
    subsetter = Subsetter(options=options)
    subsetter.populate(text=USED_TEXT)
    subsetter.subset(font)

    output_ligatures = _ligature_map(font)
    if any(output_ligatures.get(name) != name for name in USED_GLYPHS):
        raise ValueError("Subset is missing a Wysun icon ligature")
    outputs = set(output_ligatures.values())
    if outputs != USED_GLYPHS:
        raise ValueError("Subset has unexpected icon outputs: " + ", ".join(sorted(outputs)))
    if _axes(font) != axes:
        raise ValueError("Subset did not preserve all variable font axes")
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Full upstream Material Symbols Rounded TTF")
    parser.add_argument("output", type=Path, help="Subset TTF output path")
    args = parser.parse_args()
    build_subset(args.source, args.output)
    print(f"Wrote {args.output} ({args.output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
