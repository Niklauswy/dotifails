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
  - Popout host (phase 2), without `BlobGroup`, `MultiEffect` or any plugin import: `apps/shell/modules/popouts/Wrapper.qml` and `ClipWrapper.qml` from `modules/bar/popouts/Wrapper.qml` and `ClipWrapper.qml`; `PopoutState.qml` from `modules/bar/popouts/PopoutState.qml`; `Interactions.qml` and `Regions.qml` from `modules/drawers/Interactions.qml` and `Regions.qml`; the composition in `PopoutHost.qml`/`PopoutCard.qml` follows `modules/drawers/Panels.qml`; `apps/shell/utils/PopoutGeometry.js` from the geometry of `modules/bar/popouts/Wrapper.qml`
  - Dashboard (phase 2), `apps/shell/modules/dashboard/`: `Wrapper.qml`, `Content.qml`, `Tabs.qml`, `Dash.qml`, `Media.qml` and `Performance.qml` from the files of the same name in `modules/dashboard/`; `dash/Resources.qml`, `dash/DateTime.qml`, `dash/Calendar.qml` and `dash/Media.qml` from `modules/dashboard/dash/`; `performance/HeroCard.qml` and `performance/Gauge.qml` from `modules/dashboard/performance/` (the circular progress is redrawn with `QtQuick.Shapes` instead of the plugin's `CircularProgress`); `services/Media.qml` from `services/Players.qml` adapted to Wysun Music and to MPRIS players without remote artwork. The upstream fourth tab (Weather) is replaced by `Workspaces.qml` ("Escritorios"), original Wysun code over the existing Hyprland model; `Card.qml`, `IconButton.qml`, `Logic.js`, `LiveProviders.qml`, `performance/ArcPath.qml` and `services/Metrics.qml` are Wysun code written for this port.
  - `apps/shell/services/Colours.qml` from `services/Colours.qml`, adapted to Wysun's fixed-theme fallback and `scheme.json` contract
  - `apps/shell/modules/launcher/Wrapper.qml` from `modules/launcher/Wrapper.qml`
  - `apps/shell/modules/launcher/Content.qml` from `modules/launcher/Content.qml`
  - `apps/shell/modules/launcher/ContentList.qml` from `modules/launcher/ContentList.qml`
  - `apps/shell/modules/launcher/AppList.qml` from `modules/launcher/AppList.qml`
  - `apps/shell/modules/launcher/WallpaperList.qml` from `modules/launcher/WallpaperList.qml`
  - `apps/shell/modules/launcher/SearchBar.qml` from `components/controls/SearchBar.qml` and `modules/launcher/Content.qml`
  - `apps/shell/modules/launcher/items/ResultItem.qml` from `modules/launcher/items/{AppItem,ActionItem,CalcItem,SchemeItem,VariantItem,WallpaperItem}.qml`
  - `apps/shell/modules/launcher/services/M3Variants.qml` from `modules/launcher/services/M3Variants.qml`
  - `apps/shell/modules/launcher/Dispatcher.qml` from the command handling in `modules/launcher/services/{Apps,Actions,Schemes}.qml`
  - `apps/shell/modules/launcher/backend.py` from `modules/launcher/WallpaperList.qml` and `items/WallpaperItem.qml`, reduced to a read-only wallpaper list
  - `apps/shell/modules/launcher/Logic.js` from `modules/launcher/{Content,AppList}.qml`, `modules/launcher/services/{Apps,Actions,Schemes,M3Variants}.qml` and the flow of `utils/Searcher.qml`
  - `apps/shell/services/Apps.qml`, `Actions.qml` and `Schemes.qml` from the same-named `modules/launcher/services/` files

  The launcher does not include Caelestia's `utils/scripts/fzf.js`
  (BSD-3-Clause) or `utils/scripts/fuzzysort.js` (MIT); the search and
  arithmetic code in `Logic.js` is a bounded Wysun implementation. Caelestia's
  `caelestia` CLI calls, `Qalculator`, wallpaper writer, `wrap_term_launch.sh`
  and `modules/Shortcuts.qml` are not copied. Wysun uses `DesktopEntries`,
  `Wysun`'s allowlist and existing `wysun scheme set` producer instead.

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

Not ported: `NotificationServer` was ported later: the shell owns the notification bus and there is no separate daemon, `utilities/cards/Record*.qml` and the screen recorder (Wysun Recorder and its portals are used unchanged).

**Update (Wysun part 2, rebranding).** `apps/shell/` now holds the complete adapted shell, renamed to Wysun (QML modules `Wysun.*`, C++ namespace `wysun`, runtime paths and IPC). It includes the adapted C++ plugin under `apps/shell/plugin/` (GPL-3.0, base revision recorded in `apps/shell/UPSTREAM.json`, which keeps the per-file hashes of the imported tree; `apps/shell/LICENSE` is the original licence text). The runtime builder (`installer/runtime_build.py`, versions in `manifests/runtime.json`) downloads and compiles, at install time and without redistributing their source here: Quickshell (LGPL-3.0, git.outfoxxed.me/quickshell), `libcava`/cavacore (MIT, github.com/LukashonakV/cava), `m3shapes` (Apache-2.0, github.com/soramanew/m3shapes) and the wayland-protocols 1.47 XML (MIT), plus Qt 6.9.3 (LGPL-3.0) via aqtinstall. Google Sans Flex ships under its own licence in `apps/shell/assets/google-sans-flex/LICENSE`.

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
- Bundled files: `apps/wysun/assets/fonts/MaterialSymbolsRounded.ttf` (Wysun Qt apps) and the identical `apps/shell/assets/fonts/MaterialSymbolsRounded.ttf` (Caelestia shell): the complete variable font. The 224 icons that the Wysun Qt apps rely on are listed one per line in `apps/wysun/assets/fonts/material-symbols-glyphs.txt` (shared contract read by `apps/wysun/wysun_fonts.py`).
- SHA-256: `32e4011709e055596eb8d2dd0f7cb547b47c1d40ac9ecb8fad54f7f7eac202e7`.

## Rubik

- Source: [google/fonts](https://github.com/google/fonts), `ofl/rubik/Rubik[wght].ttf`.
- License: SIL Open Font License 1.1; text in [`LICENSES/OFL-Rubik.txt`](LICENSES/OFL-Rubik.txt).
- Bundled font: `apps/wysun/assets/fonts/Rubik-Variable.ttf`.
- SHA-256: `1b3a7437ba2af80e465e773ed60c5036d1ba6ace492d89046dbcf18fb31e4e88`.

## Lobe Icons (AI brand marks)

- Source: [lobehub/lobe-icons](https://github.com/lobehub/lobe-icons), npm `@lobehub/icons-static-svg` 1.97.0.
- License: MIT; text in [`LICENSES/MIT-lobe-icons.txt`](LICENSES/MIT-lobe-icons.txt).
- `apps/shell/modules/aiusage/Logos.js` keeps the 24×24 path data of the Claude, Anthropic, Codex, OpenAI, Gemini, GitHub Copilot, Cursor, DeepSeek, Mistral and Grok marks, drawn in the theme colour by the AI usage panel. The marks are trademarks of their owners and only identify each provider's account.

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
## Wysun Music native presentation (phase 7)

- Repository: [caelestia-dots/shell](https://github.com/caelestia-dots/shell), commit `507d66285e9d9fde9330adc64159cfdebb28c19a`.
- License: GPL-3.0; full text in [`LICENSES/GPL-3.0.txt`](LICENSES/GPL-3.0.txt). The reviewed upstream QML files contain no individual copyright headers; no upstream notice was removed.
- `apps/wysun/music_app_window.py` translates the cover/details separation in `modules/dashboard/Media.qml`, title/artist/seek/transport hierarchy in `modules/dashboard/media/Details.qml`, cover clipping/fallback in `components/widgets/CoverArt.qml`, and navigation grouping in `modules/nexus/NavPane.qml` to native PySide6 widgets. The local library, mpv, queue, downloads and persistence remain Wysun's existing implementation.
- `apps/wysun/music_material.py` adapts the semantic surfaces, text roles and interaction-state layering of `components/StyledRect.qml`, `StyledText.qml` and `StateLayer.qml`. It uses the existing Wysun theme watcher and shared native motion/reduced-motion implementation. No QML, M3Shapes, visualiser, blur or C++ plugin is loaded by Music.
- These are adaptations of upstream **shell widgets**, not a port of an upstream full-screen music application. Both derived files carry “Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun”. Offline Rubik (OFL) and Material Symbols Rounded (Apache-2.0) resources are described above; the Music adapter resolves packaged resources and does not download fonts.

## Wysun Files, utilities and capture native presentation (phase 7)

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Source: https://github.com/caelestia-dots/shell, commit
`507d66285e9d9fde9330adc64159cfdebb28c19a`; license: `LICENSES/GPL-3.0.txt`.
Upstream files have no individual copyright header; no notices were removed.

- `modules/nexus/NavPane.qml` and `components/{StyledRect,StyledText,StateLayer}.qml`
  inform `apps/wysun/utility_material.py`, `files_{window,visuals}.py`,
  `{notes,color,processes,connections,tools}_window.py` and `power_widgets.py`.
  These are native QWidget translations; models, filesystem and private stores
  remain Wysun's existing implementation.
- `modules/nexus/NavPane.qml`, `modules/dashboard/Media.qml`,
  `modules/dashboard/media/Details.qml`, `components/widgets/CoverArt.qml` and
  `components/{StyledRect,StyledText,StateLayer}.qml` inform
  `apps/capture/loomrec/ui/{material,layouts,components,settings}.py`. Library
  artwork/navigation and playback hierarchy change; capture/portal/media contracts stay
  in the existing backends. This is not an upstream full-screen music app.
- Files/utilities package Rubik and complete Material Symbols fallback resources
  in `apps/wysun/assets/utils-material/`, with OFL and Apache-2.0 notices.
  Capture packages its own copies under `loomrec/ui/assets/fonts/`, with
  `apps/capture/assets/licenses/{OFL-Rubik,Apache-2.0,GPL-3.0}.txt`; it does not
  import the installed Orbit application. No download or host font installation
  is needed. Shared fonts and vendor provenance are described above.

## end-4 window overview

- Repository: [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland), source commit `2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8`.
- License: GPL-3.0; full text in [LICENSES/GPL-3.0.txt](LICENSES/GPL-3.0.txt).
- `apps/shell/modules/overview/{Overview,OverviewWidget,OverviewWindow}.qml` and `OverviewGeometry.js` are a faithful port of `dots/.config/quickshell/ii/modules/ii/overview/{Overview,OverviewWidget,OverviewWindow}.qml` (the former `modules/overview/` location): compact 2x5 card centred at the top over the visible desktop, workspace tiles with per-corner radii, the animated focused-workspace indicator, live `ScreencopyView` thumbnails masked to rounded corners, centred app icons, hover and press overlays, drag between workspaces and the `Appearance.animationCurves` / `elementMoveEnter` / `elementMoveFast` timings (mapped to Wysun `Tokens.anim`). Each adapted file retains an origin/license header.
- Wysun uses its own Hypr, Colours, Tokens and ShellState services and delegates search to its existing launcher. No upstream config or service is imported. Deviations: the tile size is capped so the card never spans more than 74% of the output width (upstream `scale` 0.18 alone yields about 90% on a 1920 px output); the surface fades, scales and slides in and out (upstream has no card entry animation); window geometry honours the output's reserved edges as upstream does; the overview opens across enabled outputs with keyboard focus on the invoking output, and includes workspaces from all outputs. The diagnostic openOn route can target a single output.

## end-4 cheat sheet

- Repository: [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland), source commit `2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8`.
- License: GPL-3.0; full text in [LICENSES/GPL-3.0.txt](LICENSES/GPL-3.0.txt).
- `apps/shell/modules/cheatsheet/Cheatsheet.qml` adapts the keycap rendering and per-category columns of `dots/.config/quickshell/ii/modules/ii/cheatsheet/`. The content is not upstream's: `backend.py` is Wysun code that reads the active `hyprland.lua` and lists its real binds in English, grouped by category and without the binds that have no Wysun equivalent.

## caelestia-aw animated wallpapers (design reference only)

- Repository: [AdiAmbassador/caelestia-aw](https://github.com/AdiAmbassador/caelestia-aw), commit `aee10ac97e9edae57cbbd1b56d2b03403ccecc09`. It is a dotfiles/patch repository without a LICENSE file in the checked-out tree (the README points to GPL-3.0 for the separate `caelestia-shell-aw` and `caelestia-cli-aw` repositories, which were not used).
- Only the feature description (video/GIF wallpapers, thumbnails cached by file identity, a representative frame feeding the Material You scheme, pausing under a fullscreen window or on battery) informed the design. No code was copied or adapted: `apps/wysun/wallpaper_media.py`, `apps/shell/services/WallpaperLibrary.qml`, `apps/shell/modules/background/WallpaperVisual.qml` and `apps/shell/modules/wallpaperpicker/` are original Wysun code. The carousel layout follows a visual reference supplied for the task, not upstream code.
