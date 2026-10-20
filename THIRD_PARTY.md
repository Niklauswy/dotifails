# Third-party code and assets

## Caelestia CLI

- Repository: https://github.com/caelestia-dots/cli
- Source commit: `40fb35b5160cc61b58e303940ccb8c7bb3a6a2e3`
- License: GPL-3.0; full text in `LICENSES/GPL-3.0.txt`.
- `apps/wysun/wysun_scheme.py` adapts the scheme generation and role serialization in `src/caelestia/utils/material/generator.py`, the hue/chroma seed scoring in `src/caelestia/utils/material/score.py`, wallpaper thumbnail/mode selection in `src/caelestia/utils/wallpaper.py`, automatic variant selection in `src/caelestia/utils/colourfulness.py`, and the JSON fields in `src/caelestia/utils/scheme.py`. It uses Wysun's existing Settings wallpaper state and writes to `$XDG_STATE_HOME/wysun/scheme.json`. The native Celebi quantizer is not included; deterministic RGB median-cut quantization is implemented in Python in this file, so its seed can differ from Caelestia's.

## materialyoucolor-python

- Repository: https://github.com/T-Dynamos/materialyoucolor-python
- Source commit: `4e45f9f66552e2555bd39b6f7d3a145ec8a5624b` (version 3.0.4)
- License: MIT; notice retained at `apps/wysun/vendor/materialyoucolor/LICENSE`.
- `apps/wysun/vendor/materialyoucolor/` contains the pure-Python HCT, palette, dynamic color, scheme, blend, contrast, temperature, and utility modules used by the generator. The upstream native quantization sources and extension are excluded.

## Scope

The derived Caelestia code carries the required GPL attribution in its source header. The vendored Material You implementation retains its MIT copyright notice. Wysun's Python median-cut quantizer is original code and has no native build or install step.
