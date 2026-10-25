pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import M3Shapes
import Wysun.Config
import qs.components
import qs.services

// What a bare prefix (?, !, >, ;) shows instead of an empty list: one shape that keeps changing
// form behind the mark of what the prefix does, and a line saying how to use it.
Item {
    id: root

    required property var modelData
    required property real scale
    required property var panel

    readonly property real stage: 150 * scale
    property bool shown

    Component.onCompleted: shown = true

    Column {
        anchors.centerIn: parent
        spacing: Tokens.spacing.large
        opacity: root.shown ? 1 : 0
        scale: root.shown ? 1 : 0.9

        Behavior on opacity {
            Anim {
                type: Anim.DefaultEffects
            }
        }
        Behavior on scale {
            Anim {
                type: Anim.SlowSpatial
            }
        }

        Item {
            id: art

            anchors.horizontalCenter: parent.horizontalCenter
            width: root.stage
            height: root.stage

            // A faint echo turning the other way, so the two never line up twice.
            MaterialShape {
                anchors.centerIn: parent
                implicitSize: art.width
                shape: echoShapes[form % echoShapes.length]
                color: Colours.palette.m3tertiaryContainer
                opacity: 0.55
                rotation: -spinB.value
                animationEasing: Tokens.anim.expressiveFastSpatial
                animationDuration: Tokens.anim.durations.expressiveSlowSpatial

                readonly property var echoShapes: [MaterialShape.Sunny, MaterialShape.Cookie12Sided, MaterialShape.SoftBurst, MaterialShape.Clover4Leaf]
                property int form

                Timer {
                    interval: 2600
                    repeat: true
                    running: root.visible
                    onTriggered: parent.form++
                }
            }

            MaterialShape {
                id: body

                readonly property var forms: [MaterialShape.Cookie9Sided, MaterialShape.SoftBurst, MaterialShape.Pentagon, MaterialShape.Cookie12Sided, MaterialShape.Sunny, MaterialShape.Clover4Leaf]
                property int form

                anchors.centerIn: parent
                implicitSize: art.width * 0.72
                shape: forms[form % forms.length]
                color: Colours.palette.m3secondaryContainer
                rotation: spinA.value
                animationEasing: Tokens.anim.expressiveFastSpatial
                animationDuration: Tokens.anim.durations.expressiveDefaultSpatial

                Timer {
                    interval: 1800
                    repeat: true
                    running: root.visible
                    onTriggered: body.form++
                }
            }

            // Brand mark or symbol, upright while the shapes turn behind it.
            Image {
                anchors.centerIn: parent
                width: art.width * 0.34
                height: width
                visible: !!root.modelData.brand
                source: visible ? Quickshell.shellPath(`assets/brands/${root.modelData.brand}.svg`) : ""
                sourceSize: Qt.size(128, 128)
                fillMode: Image.PreserveAspectFit
                smooth: true
            }
            MaterialIcon {
                anchors.centerIn: parent
                visible: !root.modelData.brand
                text: root.modelData.icon ?? "search"
                fill: 1
                color: Colours.palette.m3onSecondaryContainer
                fontStyle: Tokens.font.icon.builders.large.scale(root.scale * 1.5).build()
            }

            // Slow turns and a breath, so the card is alive without asking for attention.
            QtObject {
                id: spinA

                property real value

                NumberAnimation on value {
                    running: root.visible
                    from: 0
                    to: 360
                    duration: 38000
                    loops: Animation.Infinite
                }
            }
            QtObject {
                id: spinB

                property real value

                NumberAnimation on value {
                    running: root.visible
                    from: 0
                    to: 360
                    duration: 52000
                    loops: Animation.Infinite
                }
            }

            SequentialAnimation on scale {
                running: root.visible
                loops: Animation.Infinite

                NumberAnimation {
                    to: 1.045
                    duration: 2400
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    to: 1
                    duration: 2400
                    easing.type: Easing.InOutSine
                }
            }
        }

        StyledText {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.modelData.title ?? ""
            font: Tokens.font.title.large
            color: Colours.palette.m3onSurface
        }

        StyledText {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(root.width * 0.72, 520 * root.scale)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: root.modelData.subtitle ?? ""
            font: root.panel.fontBody
            color: Colours.palette.m3onSurfaceVariant
        }

        // Things to try; typing one into the search is a click away.
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Tokens.spacing.small
            visible: (root.modelData.examples ?? []).length > 0

            Repeater {
                model: root.modelData.examples ?? []

                Rectangle {
                    id: chip

                    required property string modelData

                    width: label.implicitWidth + Tokens.padding.large * 1.4
                    height: 28 * root.scale
                    radius: height / 2
                    color: hover.containsMouse ? Colours.palette.m3secondaryContainer : Colours.palette.m3surfaceContainerHigh

                    Behavior on color {
                        CAnim {}
                    }

                    StyledText {
                        id: label

                        anchors.centerIn: parent
                        text: chip.modelData
                        font: root.panel.fontStrong
                        color: hover.containsMouse ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                    }

                    MouseArea {
                        id: hover

                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.panel.setQuery(chip.modelData + " ")
                    }
                }
            }
        }
    }
}
