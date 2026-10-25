pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import M3Shapes
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services

// Running timers (started from the launcher with "timer 10m tea"): the time left, how much of it is
// gone, and a way to stop one. Only built while there is a timer, and nothing here ticks otherwise.
StyledRect {
    id: root

    readonly property real nonAnimHeight: layout.implicitHeight + Tokens.padding.large * 2

    implicitHeight: nonAnimHeight
    radius: Tokens.rounding.large
    color: Colours.tPalette.m3surfaceContainer
    clip: true

    ColumnLayout {
        id: layout

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.large

        Repeater {
            model: Timers.timers

            RowLayout {
                id: row

                required property var modelData

                readonly property int secondsLeft: Timers.remaining(modelData)
                // The last seconds ask for attention.
                readonly property bool urgent: secondsLeft <= 10

                Layout.fillWidth: true
                spacing: Tokens.spacing.medium

                // Turns slowly while it counts, and is not still for the last seconds.
                MaterialShape {
                    id: badge

                    Layout.alignment: Qt.AlignVCenter
                    implicitSize: 44
                    shape: row.urgent ? MaterialShape.SoftBurst : MaterialShape.Cookie9Sided
                    color: row.urgent ? Colours.palette.m3tertiary : Colours.palette.m3secondaryContainer
                    animationEasing: Tokens.anim.expressiveFastSpatial
                    animationDuration: Tokens.anim.durations.expressiveDefaultSpatial

                    Behavior on color {
                        CAnim {}
                    }

                    NumberAnimation on rotation {
                        running: root.visible
                        from: 0
                        to: 360
                        duration: row.urgent ? 4000 : 16000
                        loops: Animation.Infinite
                    }

                    MaterialIcon {
                        anchors.centerIn: parent
                        text: "timer"
                        fill: 1
                        color: row.urgent ? Colours.palette.m3onTertiary : Colours.palette.m3onSecondaryContainer
                        rotation: -badge.rotation
                        fontStyle: Tokens.font.icon.large
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                    spacing: Tokens.spacing.extraSmall

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Tokens.spacing.small

                        StyledText {
                            text: Timers.format(row.secondsLeft)
                            font: Tokens.font.title.large
                            color: row.urgent ? Colours.palette.m3tertiary : Colours.palette.m3onSurface

                            Behavior on color {
                                CAnim {}
                            }
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: row.modelData.label
                            visible: text !== ""
                            font: Tokens.font.body.small
                            color: Colours.palette.m3onSurfaceVariant
                            elide: Text.ElideRight
                        }
                    }

                    // How much of it has passed; one-second steps are eased into a continuous slide.
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 6
                        radius: height / 2
                        color: Colours.palette.m3surfaceContainerHighest

                        Rectangle {
                            width: parent.width * (row.secondsLeft / row.modelData.seconds)
                            height: parent.height
                            radius: parent.radius
                            color: row.urgent ? Colours.palette.m3tertiary : Colours.palette.m3primary

                            Behavior on width {
                                NumberAnimation {
                                    duration: 1000
                                    easing.type: Easing.Linear
                                }
                            }
                            Behavior on color {
                                CAnim {}
                            }
                        }
                    }
                }

                StyledRect {
                    Layout.alignment: Qt.AlignVCenter
                    implicitWidth: 36
                    implicitHeight: 36
                    radius: Tokens.rounding.full
                    color: "transparent"

                    StateLayer {
                        radius: parent.radius
                        onClicked: Timers.cancel(row.modelData.unit)
                    }

                    MaterialIcon {
                        anchors.centerIn: parent
                        text: "close"
                        color: Colours.palette.m3onSurfaceVariant
                        fontStyle: Tokens.font.icon.small
                    }
                }
            }
        }
    }

    Behavior on implicitHeight {
        Anim {}
    }
}
