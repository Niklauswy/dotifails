// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Wrapper.qml (contenedor de tarjetas), commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import "../../" as Wysun
import "../../components" as Components

// Surface used by every dashboard card: raised tonal fill and large radius, with
// no shadow or blur (the shell does not use the Caelestia effect plugin).
// Callers lay their content out themselves and size the card with
// `layout.implicitHeight + padding * 2`.
Components.StyledRect {
    property real padding: Wysun.Appearance.spaceL
    radius: Wysun.Appearance.radiusL
    color: Wysun.Appearance.surfaceRaised
    border.width: Wysun.Appearance.borderWidth
    border.color: Wysun.Appearance.line
}
