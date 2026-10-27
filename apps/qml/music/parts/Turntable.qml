// «Ahora suena» as a record player: the sleeve (the cover) with the vinyl sliding out of it. While music plays the
// record slides further out, spins (the cover is its label) and the tonearm swings onto it; in pause the arm lifts,
// the record stops and slides back in. The light on the vinyl stays still while it turns. Reduced motion: no spin,
// positions change at once.
import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import WysunM3

Item {
    id: root

    property url cover
    property bool playing
    property color tone: Theme.m3primary
    readonly property real side: Math.min(height, width / 1.55)
    readonly property real recordSize: side * 0.94
    property real angle: 0

    implicitWidth: 420
    implicitHeight: 280

    // ------------------------------------------------------------------ record
    Item {
        id: record

        objectName: "vinyl"
        width: root.recordSize
        height: width
        y: (root.side - height) / 2
        x: root.playing ? root.side * 0.52 : root.side * 0.16

        SpringBehavior on x {
            kind: "slowSpatial"
        }

        // The disc and what turns with it.
        Item {
            anchors.fill: parent
            rotation: root.angle

            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: "#111214"        // theme-exception: a vinyl record is black in light and dark mode
            }

            // Grooves.
            Repeater {
                model: 7

                Rectangle {
                    required property int index

                    anchors.centerIn: parent
                    width: parent.width * (0.92 - index * 0.075)
                    height: width
                    radius: width / 2
                    color: "transparent"
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, index % 2 ? 0.05 : 0.09)    // theme-exception: grooves on the vinyl
                }
            }

            // The label: the cover, round.
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
                color: Qt.rgba(1, 1, 1, 0.55)      // theme-exception: label mark on the vinyl
            }
        }

        // Light that does not turn: a soft sheen across the grooves.
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeColor: "transparent"
                fillGradient: ConicalGradient {
                    centerX: record.width / 2
                    centerY: record.height / 2
                    angle: 35
                    GradientStop {
                        position: 0
                        color: Qt.rgba(1, 1, 1, 0.10)          // theme-exception: light on the vinyl
                    }
                    GradientStop {
                        position: 0.12
                        color: Qt.rgba(1, 1, 1, 0)             // theme-exception: light on the vinyl
                    }
                    GradientStop {
                        position: 0.5
                        color: Qt.rgba(1, 1, 1, 0.08)          // theme-exception: light on the vinyl
                    }
                    GradientStop {
                        position: 0.62
                        color: Qt.rgba(1, 1, 1, 0)             // theme-exception: light on the vinyl
                    }
                }
                PathAngleArc {
                    centerX: record.width / 2
                    centerY: record.height / 2
                    radiusX: record.width / 2
                    radiusY: record.height / 2
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
        }
    }

    NumberAnimation on angle {
        from: root.angle % 360
        to: root.angle % 360 + 360
        duration: Theme.duration("extraLarge") * 3.6      // a calm turn (≈ 17 rpm), not a real 33⅓
        loops: Animation.Infinite
        running: root.playing && root.visible && !Motion.reduced
    }

    // ------------------------------------------------------------------- sleeve
    Item {
        id: sleeve

        width: root.side
        height: root.side
        scale: root.playing ? 1 : 0.97

        SpringBehavior on scale {
            kind: "defaultSpatial"
        }

        RectangularShadow {
            anchors.fill: art
            radius: art.radius
            blur: 28
            spread: 2
            offset.y: 10
            color: Qt.alpha(Theme.m3shadow, 0.45)
        }

        Rectangle {
            id: art

            anchors.fill: parent
            radius: Theme.rounding.medium ?? 0
            color: root.tone
            clip: true

            Image {
                anchors.fill: parent
                source: root.cover
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 512
                sourceSize.height: 512
                asynchronous: true
                visible: status === Image.Ready
                layer.enabled: true
                layer.effect: MultiEffect {
                    maskEnabled: true
                    maskSource: sleeveMask
                }
            }
            Icon {
                anchors.centerIn: parent
                name: "album"
                size: parent.width * 0.3
                color: Theme.m3onPrimaryContainer
                visible: parent.children[0].status !== Image.Ready
            }
        }

        Rectangle {
            id: sleeveMask

            anchors.fill: art
            radius: art.radius
            visible: false
            layer.enabled: true
        }
    }

    // ------------------------------------------------------------------ tonearm
    Item {
        id: arm

        objectName: "tonearm"
        readonly property real length: root.recordSize * 0.5

        // The pivot sits beyond the top right of the record's playing position.
        x: root.side * 0.52 + root.recordSize * 1.02
        y: (root.side - root.recordSize) / 2 + root.recordSize * 0.06
        width: 1
        height: 1
        rotation: root.playing ? 4 : -22      // on the outer grooves / lifted beside the record

        SpringBehavior on rotation {
            kind: "slowSpatial"
        }

        Rectangle {
            // The arm hangs down-left from the pivot.
            x: -width / 2
            width: root.recordSize * 0.024
            height: arm.length
            radius: width / 2
            color: Theme.m3onSurfaceVariant
            transformOrigin: Item.Top
            rotation: 18

            Rectangle {
                // Headshell.
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.bottom
                anchors.topMargin: -height / 3
                width: parent.width * 2.6
                height: parent.width * 4
                radius: parent.width / 2
                color: root.tone
            }
        }

        Rectangle {
            // Pivot.
            anchors.centerIn: parent
            width: root.recordSize * 0.11
            height: width
            radius: width / 2
            color: Theme.m3surfaceContainerHighest
            border.width: root.recordSize * 0.012
            border.color: Theme.m3outline
        }
    }
}
