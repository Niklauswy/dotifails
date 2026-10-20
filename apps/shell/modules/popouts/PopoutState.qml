// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/bar/popouts/PopoutState.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import "../../components" as Components

Item {
    id: root
    required property var motion
    property bool requested: false
    property real progress: requested ? 1 : 0
    readonly property bool retained: requested || progress > 0
    readonly property string phase: requested ? (progress < 1 ? "opening" : "open") : (progress > 0 ? "closing" : "closed")
    Behavior on progress { Components.Anim { motion: root.motion; type: Components.Anim.Emphasized } }
}
