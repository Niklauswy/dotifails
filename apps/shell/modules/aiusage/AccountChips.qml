pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.services

// The visible accounts of one provider as chips (ring = share used of its tightest limit), plus "Add".
Flow {
    id: root

    required property string provider
    property string current

    signal selected(string id)
    signal addRequested

    readonly property var accounts: AiUsage.providerAccounts(provider)

    Layout.fillWidth: true
    spacing: Tokens.spacing.small

    Repeater {
        model: root.accounts.length > 1 ? root.accounts : []

        StyledRect {
            id: chip

            required property var modelData
            readonly property bool active: root.current === modelData.id
            readonly property var tight: modelData.limits?.length ? modelData.limits.reduce((m, l) => l.usedPercent > m.usedPercent ? l : m, modelData.limits[0]) : null
            readonly property var who: AiUsage.names(modelData)

            implicitWidth: row.implicitWidth + Tokens.padding.small + Tokens.padding.medium
            implicitHeight: row.implicitHeight + Tokens.padding.extraSmall * 2
            radius: Tokens.rounding.full
            color: active ? Colours.palette.m3secondaryContainer : Colours.tPalette.m3surfaceContainer
            border.width: active ? 1 : 0
            border.color: Qt.alpha(Colours.palette.m3primary, 0.4)

            StateLayer {
                radius: chip.radius
                color: Colours.palette.m3onSurface
                onClicked: root.selected(chip.modelData.id)
            }

            RowLayout {
                id: row

                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: Tokens.padding.extraSmall
                spacing: Tokens.spacing.small

                CircularProgress {
                    implicitSize: Tokens.sizes.aiUsage.barIndicatorSize
                    strokeWidth: Tokens.padding.extraSmall / 2 + 1
                    value: Math.max(0.03, (chip.tight?.usedPercent ?? 0) / 100)
                    fgColour: AiUsage.severityColour(chip.tight?.usedPercent ?? 0)
                    bgColour: Qt.alpha(Colours.palette.m3onSurface, 0.1)
                }

                StyledText {
                    text: chip.who.label
                    font: Tokens.font.label.medium
                    color: chip.active ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                }

                StyledText {
                    visible: !!chip.modelData.plan
                    text: chip.modelData.plan ?? ""
                    font: Tokens.font.label.small
                    color: Colours.palette.m3outline
                }
            }
        }
    }

    StyledRect {
        implicitWidth: add.implicitWidth + Tokens.padding.medium * 2
        implicitHeight: add.implicitHeight + Tokens.padding.extraSmall * 2
        radius: Tokens.rounding.full
        color: Colours.tPalette.m3surfaceContainer

        StateLayer {
            radius: parent.radius
            color: Colours.palette.m3onSurface
            onClicked: root.addRequested()
        }

        RowLayout {
            id: add

            anchors.centerIn: parent
            spacing: Tokens.spacing.extraSmall

            MaterialIcon {
                text: "add"
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.small
            }

            StyledText {
                text: Tr.tr("Add")
                font: Tokens.font.label.medium
                color: Colours.palette.m3onSurfaceVariant
            }
        }
    }
}
