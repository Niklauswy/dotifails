pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import "../../../services/DriveLogic.js" as Logic

// What Wysun Drive is uploading: one card per upload with its items, progress and «Cancelar».
// The link arrives as a notification (already on the clipboard) when it finishes.
ColumnLayout {
    id: root

    width: 340
    spacing: Tokens.spacing.medium

    StyledText {
        Layout.topMargin: Tokens.padding.small
        text: Drive.uploads.length > 1 ? `Subiendo a Wysun Drive · ${Drive.uploads.length}` : "Subiendo a Wysun Drive"
        font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
    }

    StyledText {
        visible: !Drive.active
        text: "Nada en curso"
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.small
    }

    Repeater {
        model: ScriptModel {
            values: Drive.uploads
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
                            text: "cloud_upload"
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
                            elide: Text.ElideMiddle
                            font: Tokens.font.title.small
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: Logic.detail(card.modelData)
                            color: Colours.palette.m3onSurfaceVariant
                            elide: Text.ElideRight
                            font: Tokens.font.body.small
                        }
                    }
                }

                StyledProgressBar {
                    Layout.fillWidth: true
                    implicitHeight: Tokens.padding.small
                    value: Logic.fraction(card.modelData)
                    indeterminate: !card.modelData.total
                }

                Repeater {
                    model: (card.modelData.items ?? []).length > 1 ? (card.modelData.items ?? []).slice(0, 4) : []

                    RowLayout {
                        id: item

                        required property var modelData

                        Layout.fillWidth: true
                        spacing: Tokens.spacing.small

                        StyledText {
                            Layout.fillWidth: true
                            text: item.modelData.name
                            elide: Text.ElideMiddle
                            font: Tokens.font.body.small
                        }

                        StyledText {
                            text: Math.round(Logic.fraction(item.modelData) * 100) + " %"
                            color: Colours.palette.m3onSurfaceVariant
                            font: Tokens.font.label.small
                        }
                    }
                }

                IconTextButton {
                    Layout.fillWidth: true
                    Layout.topMargin: Tokens.spacing.small
                    inactiveColour: Colours.palette.m3errorContainer
                    inactiveOnColour: Colours.palette.m3onErrorContainer
                    verticalPadding: Tokens.padding.small
                    icon: "cancel"
                    text: "Cancelar"
                    onClicked: Drive.cancel(card.modelData.pid)
                }
            }
        }
    }
}
