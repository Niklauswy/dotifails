import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import Quickshell
import qs.services

// Inline notice: an incident, a read error with its command, an upcoming reset or an expiring sign-in.
StyledRect {
    id: root

    property string icon: "info"
    property color tone: Colours.palette.m3primary
    property string title
    property string body
    // Monospaced command shown with a copy button, e.g. "claude /login".
    property string command
    property var details: []  // [{ name, value, colour }]

    Layout.fillWidth: true
    implicitHeight: layout.implicitHeight + Tokens.padding.medium * 2
    radius: Tokens.rounding.large
    color: Qt.alpha(tone, 0.14)

    RowLayout {
        id: layout

        anchors.fill: parent
        anchors.margins: Tokens.padding.medium
        spacing: Tokens.spacing.medium

        MaterialIcon {
            Layout.alignment: Qt.AlignTop
            text: root.icon
            fill: 1
            color: root.tone
            fontStyle: Tokens.font.icon.medium
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.extraSmall

            StyledText {
                Layout.fillWidth: true
                text: root.title
                font: Tokens.font.title.small
                wrapMode: Text.WordWrap
            }

            StyledText {
                Layout.fillWidth: true
                visible: !!root.body
                text: root.body
                font: Tokens.font.body.small
                color: Colours.palette.m3onSurfaceVariant
                wrapMode: Text.WordWrap
            }

            RowLayout {
                visible: !!root.command
                spacing: Tokens.spacing.small

                StyledRect {
                    implicitWidth: commandText.implicitWidth + Tokens.padding.small * 2
                    implicitHeight: commandText.implicitHeight + Tokens.padding.extraSmall * 2
                    radius: Tokens.rounding.small
                    color: Colours.tPalette.m3surfaceContainerHighest

                    StyledText {
                        id: commandText

                        anchors.centerIn: parent
                        text: root.command
                        font: Tokens.font.mono.small
                    }
                }

                IconButton {
                    icon: "content_copy"
                    type: IconButton.Text
                    onClicked: Quickshell.clipboardText = root.command
                }
            }

            Repeater {
                model: root.details

                RowLayout {
                    id: detail

                    required property var modelData

                    Layout.fillWidth: true

                    StyledText {
                        Layout.fillWidth: true
                        text: detail.modelData.name
                        font: Tokens.font.label.small
                        color: Colours.palette.m3onSurfaceVariant
                    }

                    StyledText {
                        text: detail.modelData.value
                        font: Tokens.font.label.small
                        color: detail.modelData.colour
                    }
                }
            }
        }
    }
}
