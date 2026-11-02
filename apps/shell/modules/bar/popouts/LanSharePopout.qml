pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import "../../../services/LanShareLogic.js" as Logic

// What Wysun LANShare is sharing: addresses and password to copy, who is in, transfers,
// the automatic shutdown, and «Dejar de compartir» for each running server.
ColumnLayout {
    id: root

    width: 340
    spacing: Tokens.spacing.medium

    StyledText {
        Layout.topMargin: Tokens.padding.small
        text: LanShare.servers.length > 1 ? `Compartiendo en la red · ${LanShare.servers.length}` : "Compartiendo en la red"
        font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
    }

    StyledText {
        visible: !LanShare.active
        text: "Nada compartido"
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.small
    }

    Repeater {
        model: ScriptModel {
            values: LanShare.servers
            objectProp: "pid"
        }

        StyledRect {
            id: card

            required property var modelData

            Layout.fillWidth: true
            implicitHeight: content.implicitHeight + Tokens.padding.large * 2
            radius: Tokens.rounding.large
            color: Colours.tPalette.m3surfaceContainerHigh

            ColumnLayout {
                id: content

                anchors.fill: parent
                anchors.margins: Tokens.padding.large
                spacing: Tokens.spacing.small

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.medium

                    StyledRect {
                        implicitWidth: Tokens.sizes.bar.innerWidth
                        implicitHeight: implicitWidth
                        radius: Tokens.rounding.medium
                        color: Colours.palette.m3primaryContainer

                        MaterialIcon {
                            anchors.centerIn: parent
                            text: card.modelData.mode === "folder" ? "folder_shared" : "share"
                            color: Colours.palette.m3onPrimaryContainer
                            fill: 1
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        StyledText {
                            Layout.fillWidth: true
                            text: card.modelData.title ?? ""
                            elide: Text.ElideRight
                            font: Tokens.font.title.small
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: Logic.access(card.modelData)
                            color: Colours.palette.m3onSurfaceVariant
                            elide: Text.ElideRight
                            font: Tokens.font.body.small
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.small

                    MaterialIcon {
                        text: "schedule"
                        color: Colours.palette.m3onSurfaceVariant
                        fontStyle: Tokens.font.icon.small
                    }

                    StyledText {
                        Layout.fillWidth: true
                        text: Logic.remaining(card.modelData, LanShare.now)
                        color: Colours.palette.m3onSurfaceVariant
                        elide: Text.ElideRight
                        font: Tokens.font.body.small
                    }
                }

                Repeater {
                    model: card.modelData.addresses ?? []

                    CopyRow {
                        required property string modelData

                        icon: "link"
                        value: modelData
                    }
                }

                CopyRow {
                    visible: !!card.modelData.password
                    icon: "key"
                    label: "Contraseña"
                    value: card.modelData.password ?? ""
                }

                StyledText {
                    Layout.fillWidth: true
                    Layout.topMargin: Tokens.spacing.extraSmall
                    text: Logic.people(card.modelData)
                    color: Colours.palette.m3onSurfaceVariant
                    wrapMode: Text.Wrap
                    font: Tokens.font.body.small
                }

                Repeater {
                    model: (card.modelData.transfers ?? []).slice(0, 3)

                    ColumnLayout {
                        id: transfer

                        required property var modelData

                        Layout.fillWidth: true
                        spacing: Tokens.spacing.extraSmall

                        StyledText {
                            Layout.fillWidth: true
                            text: Logic.transferText(transfer.modelData)
                            elide: Text.ElideMiddle
                            font: Tokens.font.body.small
                        }

                        StyledProgressBar {
                            Layout.fillWidth: true
                            implicitHeight: Tokens.padding.small
                            value: Logic.progress(transfer.modelData)
                            indeterminate: !transfer.modelData.total
                        }
                    }
                }

                IconTextButton {
                    Layout.fillWidth: true
                    Layout.topMargin: Tokens.spacing.small
                    inactiveColour: Colours.palette.m3errorContainer
                    inactiveOnColour: Colours.palette.m3onErrorContainer
                    verticalPadding: Tokens.padding.small
                    icon: "stop_circle"
                    text: "Dejar de compartir"
                    onClicked: LanShare.stop(card.modelData.pid)
                }
            }
        }
    }

    component CopyRow: RowLayout {
        id: row

        property string icon
        property string label
        property string value
        property bool copied

        Layout.fillWidth: true
        spacing: Tokens.spacing.small

        MaterialIcon {
            text: row.icon
            color: Colours.palette.m3onSurfaceVariant
            fontStyle: Tokens.font.icon.small
        }

        StyledText {
            Layout.fillWidth: true
            text: row.label ? `${row.label}: ${row.value}` : row.value
            elide: Text.ElideRight
            font: Tokens.font.mono.small
        }

        IconButton {
            type: IconButton.Text
            icon: row.copied ? "check" : "content_copy"
            font: Tokens.font.icon.small
            onClicked: {
                LanShare.copy(row.value);
                row.copied = true;
                copiedTimer.restart();
            }
        }

        Timer {
            id: copiedTimer

            interval: 1500
            onTriggered: row.copied = false
        }
    }
}
