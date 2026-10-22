pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.effects
import qs.services

// What to do with a selected region: copy, save as, annotate, read its text or cancel.
StyledRect {
    id: root

    signal copy
    signal saveAs
    signal annotate
    signal readText
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

        Action {
            primary: true
            icon: "content_copy"
            text: Tr.tr("Copy")
            key: "↵"
            onClicked: root.copy()
        }

        Action {
            icon: "save_as"
            text: Tr.tr("Save as…")
            key: "S"
            onClicked: root.saveAs()
        }

        Action {
            icon: "draw"
            text: Tr.tr("Annotate")
            key: "A"
            onClicked: root.annotate()
        }

        Action {
            icon: "text_fields"
            text: Tr.tr("Text")
            key: "T"
            onClicked: root.readText()
        }

        StyledRect {
            Layout.preferredWidth: 1
            Layout.preferredHeight: Tokens.spacing.large
            color: Colours.palette.m3outlineVariant
        }

        Action {
            icon: "close"
            key: "Esc"
            onClicked: root.cancel()
        }
    }

    component Action: StyledRect {
        id: action

        property string icon
        property string text
        property string key
        property bool primary

        signal clicked

        implicitWidth: content.implicitWidth + Tokens.padding.medium * 2
        implicitHeight: content.implicitHeight + Tokens.padding.small * 2
        radius: Tokens.rounding.full
        color: primary ? Colours.palette.m3primary : "transparent"

        StateLayer {
            radius: action.radius
            color: action.primary ? Colours.palette.m3onPrimary : Colours.palette.m3onSurface
            onClicked: action.clicked()
        }

        RowLayout {
            id: content

            anchors.centerIn: parent
            spacing: Tokens.spacing.small

            MaterialIcon {
                text: action.icon
                color: action.primary ? Colours.palette.m3onPrimary : Colours.palette.m3onSurface
                fontStyle: Tokens.font.icon.medium
            }

            StyledText {
                visible: action.text.length > 0
                text: action.text
                font: Tokens.font.label.builders.large.weight(Font.Medium).build()
                color: action.primary ? Colours.palette.m3onPrimary : Colours.palette.m3onSurface
            }

            StyledRect {
                implicitWidth: keycap.implicitWidth + Tokens.padding.small
                implicitHeight: keycap.implicitHeight + Tokens.padding.extraSmall / 2
                radius: Tokens.rounding.extraSmall
                color: action.primary ? Qt.alpha(Colours.palette.m3onPrimary, 0.18) : Colours.palette.m3surfaceContainerHighest

                StyledText {
                    id: keycap

                    anchors.centerIn: parent
                    text: action.key
                    font: Tokens.font.label.small
                    color: action.primary ? Colours.palette.m3onPrimary : Colours.palette.m3onSurfaceVariant
                }
            }
        }
    }
}
