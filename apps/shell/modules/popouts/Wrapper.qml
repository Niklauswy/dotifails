// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/bar/popouts/Wrapper.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import "../../utils/PopoutGeometry.js" as Geometry
import "../../components" as Components

// Geometry-only morph surface. Position and size are a pure function of
// `progress`; the animation lives in PopoutState so an interrupted transition
// retargets continuously instead of stacking Behaviors.
FocusScope {
    id: root
    required property var motion
    property real progress: 0
    property var originRect: ({ x: 0, y: 0, width: 72, height: 64 })
    property var targetRect: ({ x: 0, y: 0, width: 0, height: 0 })
    property real contentOpacity: 1
    default property alias content: clipper.content

    readonly property var geometry: Geometry.interpolateRect(
        originRect.x, originRect.y, originRect.width, originRect.height,
        targetRect.x, targetRect.y, targetRect.width, targetRect.height,
        motion && motion.reducedMotion ? (progress > 0 ? 1 : 0) : progress)

    x: geometry.x
    y: geometry.y
    width: geometry.width
    height: geometry.height
    visible: progress > 0
    clip: true

    ClipWrapper {
        id: clipper
        anchors.fill: parent
        opacity: root.contentOpacity
        Accessible.role: Accessible.Grouping
        Accessible.name: "Panel de Wysun"
    }
}
