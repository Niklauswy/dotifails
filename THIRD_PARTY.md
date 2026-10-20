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
- Bundled font: `apps/shell/assets/fonts/MaterialSymbolsRounded.ttf`.
- SHA-256: `32e4011709e055596eb8d2dd0f7cb547b47c1d40ac9ecb8fad54f7f7eac202e7`.

## Rubik

- Source: [google/fonts](https://github.com/google/fonts), `ofl/rubik/Rubik[wght].ttf`.
- License: SIL Open Font License 1.1; text in [`LICENSES/OFL-Rubik.txt`](LICENSES/OFL-Rubik.txt).
- Bundled font: `apps/shell/assets/fonts/Rubik-Variable.ttf`.
- SHA-256: `1b3a7437ba2af80e465e773ed60c5036d1ba6ace492d89046dbcf18fb31e4e88`.
