pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.effects
import qs.services

// First step of a recording: what to record. A screen, a window or a region.
StyledRect {
    id: root

    signal chosen(string what)
    signal cancel

    implicitWidth: row.implicitWidth + Tokens.padding.small * 2
    implicitHeight: row.implicitHeight + Tokens.padding.small * 2
    radius: Tokens.rounding.full
    color: Colours.palette.m3surfaceContainer
    border.width: 1
    border.color: Qt.alpha(Colours.palette.m3outlineVariant, 0.6)

    Elevation {
        anchors.fill: parent
        radius: root.radius
        level: 3
        z: -1
    }

    RowLayout {
        id: row

        anchors.centerIn: parent
        spacing: Tokens.spacing.extraSmall

        Mode {
            icon: "desktop_windows"
            text: Tr.tr("Screen")
            key: "1"
            onClicked: root.chosen("screen")
        }

        Mode {
            icon: "web_asset"
            text: Tr.tr("Window")
            key: "2"
            onClicked: root.chosen("window")
        }

        Mode {
            icon: "screenshot_region"
            text: Tr.tr("Area")
            key: "3"
            onClicked: root.chosen("area")
        }

        StyledRect {
            Layout.preferredWidth: 1
            Layout.preferredHeight: Tokens.spacing.large
            color: Colours.palette.m3outlineVariant
        }

        Mode {
            icon: "close"
            key: "Esc"
            onClicked: root.cancel()
        }
    }

    component Mode: StyledRect {
        id: mode

        property string icon
        property string text
        property string key

        signal clicked

        implicitWidth: content.implicitWidth + Tokens.padding.large * 2
        implicitHeight: content.implicitHeight + Tokens.padding.medium * 2
        radius: Tokens.rounding.full
        color: "transparent"

        StateLayer {
            radius: mode.radius
            onClicked: mode.clicked()
        }

        RowLayout {
            id: content

            anchors.centerIn: parent
            spacing: Tokens.spacing.small

            MaterialIcon {
                text: mode.icon
                color: Colours.palette.m3onSurface
                fontStyle: Tokens.font.icon.large
            }

            StyledText {
                visible: mode.text.length > 0
                text: mode.text
                font: Tokens.font.label.builders.large.weight(Font.Medium).build()
            }

            StyledRect {
                implicitWidth: keycap.implicitWidth + Tokens.padding.small
                implicitHeight: keycap.implicitHeight + Tokens.padding.extraSmall / 2
                radius: Tokens.rounding.extraSmall
                color: Colours.palette.m3surfaceContainerHighest

                StyledText {
                    id: keycap

                    anchors.centerIn: parent
                    text: mode.key
                    font: Tokens.font.label.small
                    color: Colours.palette.m3onSurfaceVariant
                }
            }
        }
    }
}
