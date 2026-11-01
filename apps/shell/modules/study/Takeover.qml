pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Wysun.Config
import qs.components
import qs.services

// The full-screen moment when a session starts: wallpaper colours, "Modo estudio" written from thin to
// regular, the rhythm, the allowed apps, and two Material shapes turning slowly behind.
Item {
    id: root

    property bool shown
    property var config: null
    readonly property var breaks: ({25: 5, 50: 10, 90: 20})
    readonly property int blocks: config ? (Study.blockCount(config.duration, config.rhythm) ?? 0) : 0
    readonly property string rhythmLine: config ? (blocks ? `${blocks} ${blocks > 1 ? "bloques" : "bloque"} · ` : "")
                                                  + `${config.rhythm} min de foco, ${breaks[config.rhythm]} de descanso` : ""
    readonly property var apps: (config?.allowed ?? []).map(c => Study.appName(c))
    property real weight: Font.ExtraLight
    property real spread: Tokens.spacing.medium

    onShownChanged: {
        if (shown) {
            leave.stop();
            enter.restart();
        } else {
            enter.stop();
            leave.restart();
        }
    }

    opacity: 0

    ParallelAnimation {
        id: enter

        Anim {
            target: root
            property: "opacity"
            to: 1
            type: Anim.DefaultEffects
        }
        Anim {
            target: shapes
            property: "scale"
            from: 0.35
            to: 1
            duration: Tokens.anim.durations.expressiveSlowSpatial * 2
            easing: Tokens.anim.expressiveSlowSpatial
        }
        Anim {
            target: shapes
            property: "rotation"
            from: -40
            to: 0
            duration: Tokens.anim.durations.expressiveSlowSpatial * 2
            easing: Tokens.anim.emphasizedDecel
        }
        SequentialAnimation {
            PropertyAction {
                targets: [title, line, chips]
                property: "opacity"
                value: 0
            }
            PropertyAction {
                target: root
                property: "weight"
                value: Font.ExtraLight
            }
            PauseAnimation {
                duration: Tokens.anim.durations.small
            }
            ParallelAnimation {
                Anim {
                    target: title
                    property: "opacity"
                    to: 1
                    type: Anim.DefaultEffects
                }
                Anim {
                    target: root
                    property: "weight"
                    to: Font.Medium
                    duration: Tokens.anim.durations.extraLarge
                    easing: Tokens.anim.emphasizedDecel
                }
                Anim {
                    target: root
                    property: "spread"
                    from: Tokens.spacing.medium
                    to: 0
                    duration: Tokens.anim.durations.extraLarge
                    easing: Tokens.anim.emphasizedDecel
                }
                SequentialAnimation {
                    PauseAnimation {
                        duration: Tokens.anim.durations.normal
                    }
                    Anim {
                        target: line
                        property: "opacity"
                        to: 0.8
                        type: Anim.DefaultEffects
                    }
                    Anim {
                        target: chips
                        property: "opacity"
                        to: 1
                        type: Anim.DefaultEffects
                    }
                }
            }
        }
    }

    ParallelAnimation {
        id: leave

        Anim {
            targets: [title, line, chips]
            property: "opacity"
            to: 0
            type: Anim.FastEffects
        }
        SequentialAnimation {
            PauseAnimation {
                duration: Tokens.anim.durations.small
            }
            Anim {
                target: root
                property: "opacity"
                to: 0
                type: Anim.DefaultEffects
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop {
                position: 0
                color: Colours.palette.m3primaryContainer
            }
            GradientStop {
                position: 0.55
                color: Qt.tint(Colours.palette.m3surface, Qt.alpha(Colours.palette.m3primaryContainer, 0.35))
            }
            GradientStop {
                position: 1
                color: Colours.palette.m3surface
            }
        }
    }

    Item {
        id: shapes

        anchors.centerIn: parent
        width: root.height * 1.3
        height: width

        CookieShape {
            anchors.fill: parent
            lobes: 12
            amplitude: 0.03
            breath: 0.015
            spin: -0.06
            stroke: Qt.alpha(Colours.palette.m3onPrimaryContainer, 0.08)
            strokeWidth: Tokens.padding.extraSmall / 2
            running: root.opacity > 0
        }

        CookieShape {
            anchors.centerIn: parent
            width: parent.width * 0.68
            height: width
            lobes: 9
            fill: Qt.alpha(Colours.palette.m3primary, 0.12)
            running: root.opacity > 0
        }
    }

    Column {
        anchors.centerIn: parent
        spacing: Tokens.spacing.medium

        StyledText {
            id: title

            anchors.horizontalCenter: parent.horizontalCenter
            text: "Modo estudio"
            color: Colours.palette.m3onPrimaryContainer
            font.family: Tokens.font.headline.large.family
            font.pointSize: Tokens.font.headline.large.pointSize * 2.1
            font.weight: root.weight
            font.letterSpacing: root.spread
        }

        StyledText {
            id: line

            anchors.horizontalCenter: parent.horizontalCenter
            text: root.rhythmLine
            color: Colours.palette.m3onPrimaryContainer
            font: Tokens.font.body.large
        }

        Row {
            id: chips

            anchors.horizontalCenter: parent.horizontalCenter
            topPadding: Tokens.spacing.large
            spacing: Tokens.spacing.small

            Repeater {
                model: root.apps

                StyledRect {
                    required property string modelData

                    implicitWidth: label.implicitWidth + Tokens.padding.large * 2
                    implicitHeight: label.implicitHeight + Tokens.padding.small * 2
                    radius: Tokens.rounding.full
                    color: Qt.alpha(Colours.palette.m3onPrimaryContainer, 0.1)

                    StyledText {
                        id: label

                        anchors.centerIn: parent
                        text: parent.modelData
                        color: Colours.palette.m3onPrimaryContainer
                        font: Tokens.font.label.large
                    }
                }
            }
        }
    }
}
