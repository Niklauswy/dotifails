// M3 circular progress, 48 with a 4 px stroke: a primary arc from 12 o'clock clockwise, a gap, and the
// secondaryContainer track. `indeterminate` spins while visible (still with reduced motion).
import QtQuick
import QtQuick.Shapes
import WysunM3

Item {
    id: root

    property real value: 0
    property bool indeterminate
    property real size: Metrics.circularProgressSize
    readonly property bool animating: spin.running
    readonly property real _t: Metrics.progressThickness
    readonly property real _r: (size - _t) / 2
    // The gap as an angle on this circle, plus the round caps' reach.
    readonly property real _gapDeg: (Metrics.progressGap + _t) / (2 * Math.PI * _r) * 360
    readonly property real _sweep: indeterminate ? 270 : Math.max(0, Math.min(1, value)) * 360

    implicitWidth: size
    implicitHeight: size
    width: implicitWidth
    height: implicitHeight

    Shape {
        id: shape

        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            fillColor: "transparent"
            strokeColor: Theme.m3secondaryContainer
            strokeWidth: root._t
            capStyle: ShapePath.RoundCap

            PathAngleArc {
                centerX: root.size / 2
                centerY: root.size / 2
                radiusX: root._r
                radiusY: root._r
                startAngle: -90 + root._sweep + (root._sweep > 0 ? root._gapDeg : 0)
                sweepAngle: Math.max(0, 360 - root._sweep - (root._sweep > 0 ? 2 * root._gapDeg : 0))
            }
        }

        ShapePath {
            fillColor: "transparent"
            strokeColor: root._sweep > 0 ? Theme.m3primary : "transparent"
            strokeWidth: root._t
            capStyle: ShapePath.RoundCap

            PathAngleArc {
                centerX: root.size / 2
                centerY: root.size / 2
                radiusX: root._r
                radiusY: root._r
                startAngle: -90
                sweepAngle: root._sweep
            }
        }

        RotationAnimation on rotation {
            id: spin

            from: 0
            to: 360
            duration: Theme.duration("extraLarge")
            loops: Animation.Infinite
            running: root.indeterminate && root.visible && !Motion.reduced
        }
    }
}
