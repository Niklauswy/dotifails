// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/dash/Resources.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Shapes
import "../../../" as Wysun

// One 270° arc. Kept separate from Gauge so the track and the value share the
// same geometry; antialiased curves rely on the Shape's own multisampling, not
// on a shader effect.
Shape {
    id: root
    property real sweep: 270
    property color stroke: Wysun.Appearance.line
    property real thickness: Wysun.Appearance.spaceS
    preferredRendererType: Shape.CurveRenderer
    ShapePath {
        fillColor: "transparent"
        strokeColor: root.stroke
        strokeWidth: root.thickness
        capStyle: ShapePath.RoundCap
        PathAngleArc {
            centerX: root.width / 2
            centerY: root.height / 2
            radiusX: Math.max(0, (root.width - root.thickness) / 2)
            radiusY: Math.max(0, (root.height - root.thickness) / 2)
            startAngle: 135
            sweepAngle: root.sweep
        }
    }
}
