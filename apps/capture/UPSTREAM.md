# Procedencia

Código integrado desde el proyecto local `loom`, revisión `b8488d09aab4de0a47675e3d1efd92113dbf582c`.
La fuente de desarrollo de Wysun Recorder y Wysun Screenshot es ahora `apps/capture/` dentro de `dotifails`.
La copia de origen no se elimina ni modifica. Los nombres técnicos `loomrec` y `wybieshot` se conservan para compatibilidad con proyectos, procesos, preferencias e instaladores anteriores.

## Material presentation, 2026-10-20

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Source: https://github.com/caelestia-dots/shell at
507d66285e9d9fde9330adc64159cfdebb28c19a. The upstream files have no
individual copyright headers; no notice was removed. Full license travels in
assets/licenses/GPL-3.0.txt and corresponding source in this capture release.

Navigation/surface/text/state hierarchy from modules/nexus/NavPane.qml and
components/{StyledRect,StyledText,StateLayer}.qml is translated into
loomrec/ui/material.py, layouts.py, components.py and settings.py, and
wybieshot/ui/main.py. Preview/details grouping also draws from
modules/dashboard/Media.qml, dashboard/media/Details.qml and
components/widgets/CoverArt.qml. These are native PySide6 translations of shell
widgets, not an upstream capture or full-screen music application. Existing
models, portals, permission flow, projects and finalization are unchanged.
Rubik (OFL) and Material Symbols Rounded (Apache-2.0) are bundled under
loomrec/ui/assets/fonts, with their licenses under assets/licenses. The capture
release reads the shared scheme independently and imports no Orbit app code.
