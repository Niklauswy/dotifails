# Third-party code and assets

## Caelestia Shell

- Repository: [caelestia-dots/shell](https://github.com/caelestia-dots/shell)
- Source commit: `507d66285e9d9fde9330adc64159cfdebb28c19a`
- License: GNU GPL version 3; complete text in [`LICENSES/GPL-3.0.txt`](LICENSES/GPL-3.0.txt).
- Adapted files (each QML file carries a source and license header):
  - `apps/shell/components/Anim.qml` from `components/Anim.qml`
  - `apps/shell/components/AnchorAnim.qml` from `components/AnchorAnim.qml`
  - `apps/shell/components/StyledRect.qml` from `components/StyledRect.qml`
  - `apps/shell/components/StyledText.qml` from `components/StyledText.qml`
  - `apps/shell/modules/rail/Rail.qml` from `modules/bar/Bar.qml`
  - `apps/shell/modules/frame/ScreenFrame.qml` from `modules/drawers/ContentWindow.qml` and `modules/drawers/Exclusions.qml`
  - `apps/shell/modules/popouts/PopoutHost.qml` and `PopoutCard.qml` from `modules/drawers/ContentWindow.qml`
  - `apps/shell/services/Colours.qml` from `services/Colours.qml`, adapted to Wysun's fixed-theme fallback and `scheme.json` contract

### Phase 4: notifications, OSD, session and quick settings

Marked in every file as "Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun". Source commit for all rows: `507d66285e9d9fde9330adc64159cfdebb28c19a` (upstream files carry no per-file notices; the repository licence is GPL-3.0). Origin → destination:

| Origin (caelestia-dots/shell) | Destination (`apps/shell/`) |
| --- | --- |
| `modules/sidebar/NotifDock.qml`, `modules/notifications/Content.qml` | `modules/notifications/NotificationCenter.qml` |
| `modules/notifications/Notification.qml` | `modules/notifications/NotificationCard.qml` |
| `modules/osd/Wrapper.qml`, `modules/osd/Content.qml` | `modules/osd/Osd.qml`, `OsdState.qml`, `OsdHost.qml`, `OsdContent.qml`, `LevelBar.qml` |
| `modules/session/Content.qml` | `modules/session/SessionMenu.qml` |
| `modules/utilities/Wrapper.qml`, `Content.qml` | `modules/quicksettings/QuickSettings.qml`, `Content.qml`, `SectionCard.qml` |
| `modules/utilities/cards/Toggles.qml`, `cards/IdleInhibit.qml` | `modules/quicksettings/Toggles.qml`, `ControlButton.qml`, `IdleInhibit.qml` |
| `modules/drawers/ContentWindow.qml` | `modules/quicksettings/SurfacePanel.qml` |
| `modules/bar/popouts/{AudioPopout,Battery,Bluetooth,Network}.qml` | `modules/quicksettings/{AudioPopout,Battery,Bluetooth,Network}.qml`, `LevelSlider.qml` |
| `services/Audio.qml` (without `CavaProvider`) | `services/Audio.qml` (PipeWire default nodes only) |
| `services/Brightness.qml` | `services/Brightness.qml` (one backlight, sysfs via `FileView`, writes through `brightnessctl`) |
| `services/Nmcli.qml` | `services/Nmcli.qml`, `services/desktop_controls.py` (one-shot `nmcli`) |
| `services/NotifData.qml`, `services/Notifs.qml` | `services/NotifData.qml`, `services/Notifs.qml` (presentation model only) |

Not ported: `NotificationServer` (Dunst stays the only D-Bus owner and keeps its toasts), `CavaProvider`, the Caelestia C++ plugin, `utilities/cards/Record*.qml` and the screen recorder (Wysun Recorder and its portals are used unchanged).

The Caelestia C++ plugin, `qt6-m3shapes`, `libcava`, and Google Sans Flex are not included. The shell uses Quickshell 0.3.0 APIs supplied by Debian.

## Caelestia CLI

- Repository: [caelestia-dots/cli](https://github.com/caelestia-dots/cli)
- Source commit: `40fb35b5160cc61b58e303940ccb8c7bb3a6a2e3`
- License: GPL-3.0; full text in [`LICENSES/GPL-3.0.txt`](LICENSES/GPL-3.0.txt).
- `apps/wysun/wysun_scheme.py` adapts the scheme generation and role serialization in `src/caelestia/utils/material/generator.py`, the hue/chroma seed scoring in `src/caelestia/utils/material/score.py`, wallpaper thumbnail/mode selection in `src/caelestia/utils/wallpaper.py`, automatic variant selection in `src/caelestia/utils/colourfulness.py`, and the JSON fields in `src/caelestia/utils/scheme.py`. It uses Wysun's existing Settings wallpaper state and writes to `$XDG_STATE_HOME/wysun/scheme.json`. The native Celebi quantizer is not included; deterministic RGB median-cut quantization is implemented in Python in this file, so its seed can differ from Caelestia's.

## materialyoucolor-python

- Repository: [T-Dynamos/materialyoucolor-python](https://github.com/T-Dynamos/materialyoucolor-python)
- Source commit: `4e45f9f66552e2555bd39b6f7d3a145ec8a5624b` (version 3.0.4)
- License: MIT; notice retained at `apps/wysun/vendor/materialyoucolor/LICENSE`.
- `apps/wysun/vendor/materialyoucolor/` contains the pure-Python HCT, palette, dynamic color, scheme, blend, contrast, temperature, and utility modules used by the generator. The upstream native quantization sources and extension are excluded.

## Material Symbols Rounded

- Source: [google/material-design-icons](https://github.com/google/material-design-icons), `variablefont/MaterialSymbolsRounded[FILL,GRAD,opsz,wght].ttf`.
- License: Apache License 2.0; text in [`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt).
- Bundled file: `apps/shell/assets/fonts/MaterialSymbolsRounded.ttf`, a 661,972-byte variable-font subset. It keeps the `FILL`, `GRAD`, `opsz`, and `wght` axes and the 224 icons listed one per line in `apps/shell/assets/fonts/material-symbols-glyphs.txt` (16 for Music and 208 common shell/Qt actions). That list is the shared contract read by the subset tool and by `apps/wysun/wysun_fonts.py`.
- Regenerate from the full upstream font with the optional developer tool `apps/shell/tools/subset_material_symbols.py` and FontTools 4.67.0 or newer. FontTools is not a runtime dependency. Add a new icon to the glyph list first; the tool rejects unknown or duplicated names.
- SHA-256: `27b2d4142c1b71dac2fd29428b0649aa47bd7cd4f27f32f14cfb0bfbead1bdfa`.

## Rubik

- Source: [google/fonts](https://github.com/google/fonts), `ofl/rubik/Rubik[wght].ttf`.
- License: SIL Open Font License 1.1; text in [`LICENSES/OFL-Rubik.txt`](LICENSES/OFL-Rubik.txt).
- Bundled font: `apps/shell/assets/fonts/Rubik-Variable.ttf`.
- SHA-256: `1b3a7437ba2af80e465e773ed60c5036d1ba6ace492d89046dbcf18fb31e4e88`.

## Scope

Derived Caelestia code carries GPL attribution in its source headers and in this file. The vendored Material You implementation retains its MIT copyright notice. Wysun's Python median-cut quantizer is original code and has no native build or install step.
