// A vinyl record with the artwork as its label. `spinning` speeds it up to a calm 20 rpm and lets it coast to a
// stop (it never jumps); the light on the grooves stays still while it turns. Reduced motion: it does not turn.
import QtQuick
import QtQuick.Shapes
import WysunM3

Item {
    id: root

    property url cover
    property color tone: Theme.m3primary
    property bool spinning
    property real angle: 0
    // Degrees per second; animated so the platter spins up and coasts down.
    property real speed: spinning && !Motion.reduced ? 120 : 0

    implicitWidth: 320
    implicitHeight: 320

    Behavior on speed {
        NumberAnimation {
            duration: Motion.reduced ? 0 : Theme.duration("extraLarge") * (root.spinning ? 0.9 : 1.6)
            easing.type: root.spinning ? Easing.InOutQuad : Easing.OutCubic
        }
    }

    FrameAnimation {
        running: root.speed > 0.5 && root.visible
        onTriggered: root.angle = (root.angle + root.speed * frameTime) % 360
    }

    // The disc and what turns with it.
    Item {
        anchors.fill: parent
        rotation: root.angle

        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: "#0e0f11"        // theme-exception: a vinyl record is black in light and dark mode
        }

        // Grooves: fine rings in bands, with the gaps between songs.
        Repeater {
            model: 14

            Rectangle {
                required property int index

                anchors.centerIn: parent
                width: parent.width * (0.95 - index * 0.04)
                height: width
                radius: width / 2
                color: "transparent"
                border.width: index % 5 === 4 ? 2 : 1
                border.color: Qt.rgba(1, 1, 1, index % 5 === 4 ? 0.02 : index % 2 ? 0.045 : 0.075)    // theme-exception: grooves on the vinyl
            }
        }

        // A thin ring of the record's colour where the label meets the grooves.
        Rectangle {
            anchors.centerIn: parent
            width: parent.width * 0.42
            height: width
            radius: width / 2
            color: "transparent"
            border.width: Math.max(1, parent.width * 0.006)
            border.color: Qt.alpha(root.tone, 0.7)
        }

        Cover {
            anchors.centerIn: parent
            width: parent.width * 0.38
            height: width
            source: root.cover
            shape: "circle"
            fill: root.tone
            placeholderIcon: "album"
        }

        // A mark on the label so the turning reads even with a plain cover.
        Rectangle {
            x: parent.width / 2 - width / 2
            y: parent.height * 0.33
            width: parent.width * 0.012
            height: parent.height * 0.05
            radius: width / 2
            color: Qt.rgba(1, 1, 1, 0.6)      // theme-exception: label mark on the vinyl
        }
    }

    // Light that does not turn: two soft sheens across the grooves, tinted by the record's colour.
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: "transparent"
            fillGradient: ConicalGradient {
                centerX: root.width / 2
                centerY: root.height / 2
                angle: 40
                GradientStop {
                    position: 0
                    color: Qt.rgba(1, 1, 1, 0.16)          // theme-exception: light on the vinyl
                }
                GradientStop {
                    position: 0.09
                    color: Qt.rgba(1, 1, 1, 0)             // theme-exception: light on the vinyl
                }
                GradientStop {
                    position: 0.41
                    color: Qt.rgba(1, 1, 1, 0)             // theme-exception: light on the vinyl
                }
                GradientStop {
                    position: 0.5
                    color: Qt.alpha(root.tone, 0.22)
                }
                GradientStop {
                    position: 0.59
                    color: Qt.rgba(1, 1, 1, 0)             // theme-exception: light on the vinyl
                }
                GradientStop {
                    position: 0.91
                    color: Qt.rgba(1, 1, 1, 0)             // theme-exception: light on the vinyl
                }
                GradientStop {
                    position: 1
                    color: Qt.rgba(1, 1, 1, 0.16)          // theme-exception: light on the vinyl
                }
            }
            PathAngleArc {
                centerX: root.width / 2
                centerY: root.height / 2
                radiusX: root.width / 2
                radiusY: root.height / 2
                startAngle: 0
                sweepAngle: 360
            }
        }
    }

    // Spindle.
    Rectangle {
        anchors.centerIn: parent
        width: parent.width * 0.03
        height: width
        radius: width / 2
        color: Theme.m3surfaceContainerHighest
        border.width: 1
        border.color: Theme.m3outline
    }
}
