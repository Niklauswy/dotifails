# Wysun sobre Caelestia

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.

La base original completa corresponde a la revisión de `UPSTREAM.json`,
con hashes por archivo importado. Se conserva `LICENSE` íntegra. La interfaz
anterior queda recuperable en el checkpoint local `3e3508ff`. Esta rama no
está desplegada. Las adaptaciones y requisitos de ejecución se registran aquí.

## Runtime paralelo

`wysun/runtime.sh` arranca el Quickshell compilado contra Qt 6.9.3 desde
`$XDG_DATA_HOME/wysun/caelestia-runtime` (o `WYSUN_CAEL_RUNTIME`), con el plugin
Caelestia en `caelestia/lib/qt6/qml`. No reemplaza Qt ni el Quickshell activo.

Compatibilidad con Qt 6.9: `StyledSpinBox` implementa su propio `DoubleSpinBox`
(Qt 6.9 no lo trae) y `Elevation` acepta radios por esquina pero usa un único
radio. El plugin necesita `#include <ranges>` explícito y `QJsonObject` sin
`asKeyValueRange`.
