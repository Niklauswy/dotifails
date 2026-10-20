// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/bar/popouts/Wrapper.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import "../../utils/PopoutGeometry.js" as Geometry
import "../../" as Wysun

// Geometry-only morph surface. Position and size are a pure function of
// `progress`; the animation lives in PopoutState, so an interrupted transition
// retargets from the current value instead of restarting. The rounded frame is
// drawn here (a plain Rectangle clips only to its rectangle, so the content is
// inset by the frame border to stay inside the rounded corners).
FocusScope {
    id: root
    required property var motion
    property real progress: 0
    property var originRect: ({ x: 0, y: 0, width: 72, height: 64 })
    property var targetRect: ({ x: 0, y: 0, width: 0, height: 0 })
    property real contentOpacity: 1
    default property alias content: clipper.content
    signal escapePressed()

    // Reduced motion replaces the morph by a short fade of the final geometry.
    readonly property real geometryProgress: motion && motion.reducedMotion ? (progress > 0 ? 1 : 0) : progress
    readonly property var geometry: Geometry.interpolateRect(
        originRect.x, originRect.y, originRect.width, originRect.height,
        targetRect.x, targetRect.y, targetRect.width, targetRect.height,
        geometryProgress)

    x: geometry.x
    y: geometry.y
    width: geometry.width
    height: geometry.height
    visible: progress > 0
    opacity: motion && motion.reducedMotion ? Math.max(0, Math.min(1, progress)) : 1

    Keys.onEscapePressed: event => { event.accepted = true; root.escapePressed(); }

    Rectangle {
        anchors.fill: parent
        radius: Wysun.Appearance.radiusL
        color: Wysun.Appearance.materialMid
        border.width: Wysun.Appearance.borderWidth
        border.color: Wysun.Appearance.materialEdge
        antialiasing: true
    }

    ClipWrapper {
        id: clipper
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.borderWidth
        contentX: root.targetRect.x - root.x - Wysun.Appearance.borderWidth
        contentY: root.targetRect.y - root.y - Wysun.Appearance.borderWidth
        contentWidth: root.targetRect.width
        contentHeight: root.targetRect.height
        opacity: root.contentOpacity
        Accessible.role: Accessible.Grouping
        Accessible.name: "Panel de Wysun"
    }
}
