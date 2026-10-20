// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/bar/popouts/Wrapper.qml; ClipWrapper.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import "../../components" as Components

FocusScope {
    id: root
    required property var motion
    property bool requested: false
    property real originX: 0
    property real originY: 0
    property real originWidth: 0
    property real originHeight: 0
    property real targetX: 0
    property real targetY: 0
    property real targetWidth: 0
    property real targetHeight: 0
    property real progress: 0
    default property alias content: clipper.data
    readonly property bool retained: requested || progress > 0
    x: requested ? targetX : originX
    y: requested ? targetY : originY
    width: requested ? targetWidth : originWidth
    height: requested ? targetHeight : originHeight
    // Each geometry animation retargets from its current value, including when
    // a second invocation changes the origin/monitor during an opening/close.
    Behavior on x { Components.Anim { motion: root.motion; duration: root.motion.reducedMotion ? 0 : root.motion.morph; type: Components.Anim.Emphasized } }
    Behavior on y { Components.Anim { motion: root.motion; duration: root.motion.reducedMotion ? 0 : root.motion.morph; type: Components.Anim.Emphasized } }
    Behavior on width { Components.Anim { motion: root.motion; duration: root.motion.reducedMotion ? 0 : root.motion.morph; type: Components.Anim.Emphasized } }
    Behavior on height { Components.Anim { motion: root.motion; duration: root.motion.reducedMotion ? 0 : root.motion.morph; type: Components.Anim.Emphasized } }
    ClipWrapper { id: clipper; anchors.fill: parent }
}
