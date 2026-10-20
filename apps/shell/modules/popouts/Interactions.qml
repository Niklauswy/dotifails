// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/drawers/Interactions.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick

MouseArea {
    id: root
    required property var controller
    acceptedButtons: Qt.AllButtons
    // Press is consumed on this output; it must never activate an underlying
    // application on release after closing the panel.
    onClicked: root.controller.close()
}
