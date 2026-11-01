pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes

// Material "cookie" shape whose lobes breathe and slowly turn while `running`.
Shape {
    id: root

    property int lobes: 9
    property real amplitude: 0.055
    property real breath: 0.025
    // Radians per second.
    property real spin: 0.11
    property color fill: "transparent"
    property color stroke: "transparent"
    property real strokeWidth: 0
    property bool running
    property real t

    readonly property real size: Math.min(width, height)
    readonly property var points: {
        const c = size / 2, r0 = size / 2 / (1 + amplitude + breath), out = [];
        const amp = amplitude + breath * Math.sin(t * 1.1), rot = t * spin;
        for (let i = 0; i <= 180; i++) {
            const a = i / 180 * Math.PI * 2, r = r0 * (1 + amp * Math.cos(lobes * (a + rot)));
            out.push(Qt.point(c + r * Math.cos(a), c + r * Math.sin(a)));
        }
        return out;
    }

    preferredRendererType: Shape.CurveRenderer

    FrameAnimation {
        running: root.running && root.visible
        onTriggered: root.t += frameTime
    }

    ShapePath {
        fillColor: root.fill
        strokeColor: root.stroke
        strokeWidth: root.strokeWidth

        PathPolyline {
            path: root.points
        }
    }
}
