pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.services

// Picks the account of one provider, in the same language as the provider tabs: equal cells with
// the name over a meter of its tightest limit, and a quiet button to add another account.
RowLayout {
    id: root

    required property string provider
    property string current

    signal selected(string id)
    signal addRequested

    readonly property var accounts: AiUsage.providerAccounts(provider)
    readonly property int columns: Math.max(1, Math.min(accounts.length, 3))

    Layout.fillWidth: true
    spacing: Tokens.spacing.small

    // With one account there is nothing to pick: its name is right below.
    Item {
        Layout.fillWidth: true
        visible: root.accounts.length < 2
    }

    StyledRect {
        Layout.fillWidth: true
        visible: root.accounts.length > 1
        implicitHeight: cells.implicitHeight + Tokens.padding.extraSmall * 2
        radius: Tokens.rounding.large
        color: Colours.tPalette.m3surfaceContainer

        Flow {
            id: cells

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Tokens.padding.extraSmall
            spacing: Tokens.spacing.extraSmall

            Repeater {
                model: root.accounts.length > 1 ? root.accounts : []

                StyledRect {
                    id: cell

                    required property var modelData
                    readonly property bool active: root.current === modelData.id
                    readonly property var tight: modelData.limits?.length ? modelData.limits.reduce((m, l) => l.usedPercent > m.usedPercent ? l : m, modelData.limits[0]) : null
                    readonly property real shown: AiUsage.settings.showUsed ? (tight?.usedPercent ?? 0) : 100 - (tight?.usedPercent ?? 0)
                    readonly property color foreground: active ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant

                    width: (cells.width - cells.spacing * (root.columns - 1)) / root.columns
                    implicitHeight: content.implicitHeight + Tokens.padding.small * 2
                    radius: Tokens.rounding.medium
                    color: active ? Colours.palette.m3secondaryContainer : "transparent"

                    Behavior on color {
                        CAnim {}
                    }

                    StateLayer {
                        radius: cell.radius
                        color: cell.foreground
                        onClicked: root.selected(cell.modelData.id)
                    }

                    ColumnLayout {
                        id: content

                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: Tokens.padding.medium
                        anchors.rightMargin: Tokens.padding.medium
                        spacing: Tokens.spacing.extraSmall

                        StyledText {
                            Layout.fillWidth: true
                            text: AiUsage.names(cell.modelData).label
                            font: Tokens.font.label.builders.medium.weight(cell.active ? Font.DemiBold : Font.Medium).build()
                            color: cell.foreground
                            elide: Text.ElideRight
                        }

                        StyledRect {
                            Layout.fillWidth: true
                            implicitHeight: Tokens.sizes.aiUsage.modelBarHeight
                            radius: Tokens.rounding.full
                            opacity: cell.tight ? 1 : 0
                            color: Qt.alpha(cell.foreground, 0.2)

                            StyledRect {
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                width: parent.width * Math.max(0, Math.min(1, cell.shown / 100))
                                radius: Tokens.rounding.full
                                color: AiUsage.severityColour(cell.tight?.usedPercent ?? 0)
                            }
                        }
                    }
                }
            }
        }
    }

    IconButton {
        icon: "person_add"
        type: IconButton.Text
        onClicked: root.addRequested()
    }
}
