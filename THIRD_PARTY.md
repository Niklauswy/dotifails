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
- Bundled file: `apps/shell/assets/fonts/MaterialSymbolsRounded.ttf`, a 34,532-byte variable-font subset. It keeps the `FILL`, `GRAD`, `opsz`, and `wght` axes and the nine Wysun icon ligatures: `dashboard`, `volume_off`, `volume_mute`, `volume_up`, `wifi`, `battery_alert`, `battery_full`, `power_settings_new`, and `close`.
- Regenerate from the full upstream font with the optional developer tool `apps/shell/tools/subset_material_symbols.py` and FontTools 4.67.0 or newer. FontTools is not a runtime dependency.
- SHA-256: `538ef0eec31455a2423f014feb0d9905e39452ed8097bf64c6253927fb08dcc8`.
- Further optimization is pending; the bundled variable font remains unchanged because FontTools is not installed in the host environment.

## Rubik

- Source: [google/fonts](https://github.com/google/fonts), `ofl/rubik/Rubik[wght].ttf`.
- License: SIL Open Font License 1.1; text in [`LICENSES/OFL-Rubik.txt`](LICENSES/OFL-Rubik.txt).
- Bundled font: `apps/shell/assets/fonts/Rubik-Variable.ttf`.
- SHA-256: `1b3a7437ba2af80e465e773ed60c5036d1ba6ace492d89046dbcf18fb31e4e88`.

## Scope

Derived Caelestia code carries GPL attribution in its source headers and in this file. The vendored Material You implementation retains its MIT copyright notice. Wysun's Python median-cut quantizer is original code and has no native build or install step.

## Caelestia Shell — Wysun phase 5 background and lock presentation

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Source: https://github.com/caelestia-dots/shell at
`507d66285e9d9fde9330adc64159cfdebb28c19a`; full license:
[`LICENSES/GPL-3.0.txt`](LICENSES/GPL-3.0.txt). The upstream source files listed
below have no individual copyright header; their project GPL notice is retained.

| Upstream source | Wysun destination | Adaptation |
| --- | --- | --- |
| `modules/background/Background.qml` | `apps/shell/modules/background/Background.qml`, `BackgroundPolicy.js`; `apps/shell/Desktop.qml` integration | One passive surface per output; nine clock positions, local fullscreen policy, loader lifecycle on hotplug |
| `modules/background/Wallpaper.qml`, `services/Wallpapers.qml` | `apps/shell/modules/background/Wallpaper.qml`, `BackgroundPolicy.js` | Local static images and output selection from existing preferences; no CLI, IPC, shaders, video or colour producer |
| `modules/background/DesktopClock.qml` | `apps/shell/modules/background/DesktopClock.qml` | Material token plate, hour/minute/date layout, Spanish locale, scaled small-output layout; no blur or idle animation |
| `services/Time.qml` | `apps/shell/modules/background/Time.qml` | Wall clock at minute precision; instantiated only while the optional clock is visible |
| `modules/lock/Center.qml`, `Content.qml`, `center/PasswordInput.qml`, `center/StateMessage.qml` | `apps/wysun/screen_lock.py`, `bin/wysun-lock` | PySide6 translation of centred presentation and normal/verifying/cleared/error colour hierarchy to swaylock options (default backend); no authentication code copied |
| `modules/lock/Center.qml`, `Content.qml`, `center/Clock.qml`, `center/InputField.qml`, `center/StateMessage.qml` | `apps/shell/modules/lock/LockPanel.qml`, `LockPolicy.js`, `OutputLock.qml` | Opt-in QML presentation: centred date/clock column, pill password field with masked buffer, Spanish state messages, per-output scaling; Wysun tokens and Rubik instead of upstream colours/fonts |
| `modules/lock/Media.qml` | `apps/shell/modules/lock/LockMedia.qml` | Opt-in title/artist/transport card from the active MPRIS player; no cover art, no cava |

The existing swaylock readiness, failure recovery and suspend sequencing remain
authoritative for the default backend. The opt-in QML backend (`apps/shell/lock.qml`,
`apps/shell/modules/lock/`) is a Wysun-original implementation of the session lock
(`WlSessionLock`) and PAM client (`PamContext`, packaged service
`apps/shell/config/pam.d/wysun-lock`); it takes only visual structure from the files
above. `LockRoot.qml`, `LockAuth.qml`, `LockTheme.qml`, the readiness marker and
`bin/wysun-lock` selection logic are not copies of upstream code.
Stock swaylock cannot render Caelestia's clock/profile/input pill, side columns or
`Media.qml`; with the default backend these are **not ported**. Media, notifications,
avatars and wallpaper are not exposed on lock unless the user opts in to the media
card. `Lock.qml`, `Pam.qml`, `LockSurface.qml`, unlock IPC, `Visualiser.qml`, cava and
screencopy are excluded. Swaylock supplies native status strings and font lookup;
Rubik is requested, using its fontconfig fallback if unavailable in that process.
Material Symbols glyphs used by phase 5: none (labels are text); the font subset is
not changed.
