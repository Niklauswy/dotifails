# Third-party assets and adapted code

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

## Material Symbols Rounded

- Source: [google/material-design-icons](https://github.com/google/material-design-icons), `variablefont/MaterialSymbolsRounded[FILL,GRAD,opsz,wght].ttf`.
- License: Apache License 2.0; text in [`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt).
- Bundled file: `apps/shell/assets/fonts/MaterialSymbolsRounded.ttf`, a 34,532-byte variable-font subset. It keeps the `FILL`, `GRAD`, `opsz`, and `wght` axes and the nine Wysun icon ligatures: `dashboard`, `volume_off`, `volume_mute`, `volume_up`, `wifi`, `battery_alert`, `battery_full`, `power_settings_new`, and `close`.
- Regenerate from the full upstream font with the optional developer tool `apps/shell/tools/subset_material_symbols.py` and FontTools 4.67.0 or newer. FontTools is not a runtime dependency.
- SHA-256: `538ef0eec31455a2423f014feb0d9905e39452ed8097bf64c6253927fb08dcc8`.

## Rubik

- Source: [google/fonts](https://github.com/google/fonts), `ofl/rubik/Rubik[wght].ttf`.
- License: SIL Open Font License 1.1; text in [`LICENSES/OFL-Rubik.txt`](LICENSES/OFL-Rubik.txt).
- Bundled font: `apps/shell/assets/fonts/Rubik-Variable.ttf`.
- SHA-256: `1b3a7437ba2af80e465e773ed60c5036d1ba6ace492d89046dbcf18fb31e4e88`.
