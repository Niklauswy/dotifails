// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/drawers/Interactions.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick

// Full-output scrim. Clicks on the card never reach this MouseArea because the
// card is a sibling above it; clicks outside the card close the surface and
// are consumed so they cannot activate the application below on release.
MouseArea {
    id: root
    required property var controller
    property bool active: true
    anchors.fill: parent
    acceptedButtons: active ? Qt.AllButtons : Qt.NoButton
    hoverEnabled: true
    onClicked: if (root.active) root.controller.close()
}
