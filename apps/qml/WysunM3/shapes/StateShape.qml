// An M3 Expressive shape behind an icon that changes with a process state: working (R) a nine-sided cookie that
// turns, waiting (S) a circle, paused (T) a rounded square, zombie (Z) a burst, a group (G) a sunny shape.
// The change morphs with the default spatial spring (ShapeEmblem). Put the icon inside as content.
// A working shape turns one lobe (a ninth of a turn, so it looks seamless) each time nudge() is called — typically
// once per new sample — instead of spinning forever: an idle window then renders nothing between samples.
import QtQuick
import WysunM3

Item {
    id: root

    property string state
    property color color: Theme.m3secondaryContainer
    property real size: Metrics.emblemSize
    default property alias content: emblem.content
    readonly property string shapeName: ({ R: "cookie", S: "circle", D: "circle", T: "squircle", t: "squircle", Z: "burst", G: "sunny" })[state] ?? "circle"
    readonly property bool spinning: state === "R" && !Motion.reduced

    // One bounded step of the working turn; does nothing in any other state or with reduced motion.
    function nudge(): void {
        if (!spinning || !visible)
            return;
        turn.from = emblem.rotation % 360;
        turn.to = turn.from + 40;
        turn.restart();
    }

    implicitWidth: size
    implicitHeight: size

    ShapeEmblem {
        id: emblem

        anchors.centerIn: parent
        size: root.size
        shape: root.shapeName
        color: root.color

        RotationAnimator {
            id: turn

            target: emblem
            duration: Motion.ms("defaultEffects")
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Motion.bezier("standard")
        }
    }
}
