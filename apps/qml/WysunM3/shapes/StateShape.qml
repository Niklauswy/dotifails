// An M3 Expressive shape behind an icon that changes with a process state: working (R) a nine-sided cookie that
// turns slowly, waiting (S) a circle, paused (T) a rounded square, zombie (Z) a burst, a group (G) a sunny shape.
// The change morphs with the default spatial spring (ShapeEmblem). Put the icon inside as content.
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

    implicitWidth: size
    implicitHeight: size

    ShapeEmblem {
        id: emblem

        anchors.centerIn: parent
        size: root.size
        shape: root.shapeName
        color: root.color

        RotationAnimator on rotation {
            running: root.spinning
            loops: Animation.Infinite
            from: 0
            to: 360
            duration: Theme.duration("extraLarge") * 14
        }
    }
}
