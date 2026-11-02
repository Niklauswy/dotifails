pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services
import "Format.js" as Format

// Running agents: folder and branch, account, model, working or waiting, cost and age.
// A row whose window can be found focuses it.
ColumnLayout {
    id: root

    property var agents: []
    property real now: Date.now()

    visible: agents.length > 0
    Layout.fillWidth: true
    spacing: 0

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Tokens.padding.small
        Layout.rightMargin: Tokens.padding.small
        Layout.bottomMargin: Tokens.spacing.extraSmall

        StyledText {
            Layout.fillWidth: true
            // TRANSLATORS: %1 = number of running agent sessions
            text: Tr.tr("Active sessions · %1").arg(root.agents.length)
            font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
            color: Colours.palette.m3onSurfaceVariant
        }
    }

    Repeater {
        model: root.agents

        Item {
            id: session

            required property var modelData
            readonly property var account: AiUsage.account(modelData.accountId ?? "")
            readonly property string window: AiUsage.sessionWindow(modelData)
            readonly property string folder: (modelData.cwd ?? "").split("/").filter(Boolean).pop() ?? ""

            Layout.fillWidth: true
            implicitHeight: row.implicitHeight + Tokens.padding.small * 2

            StateLayer {
                disabled: !session.window
                radius: Tokens.rounding.medium
                color: Colours.palette.m3onSurface
                onClicked: AiUsage.focusSession(session.modelData)
            }

            RowLayout {
                id: row

                anchors.fill: parent
                anchors.leftMargin: Tokens.padding.small
                anchors.rightMargin: Tokens.padding.small
                spacing: Tokens.spacing.medium

                StyledRect {
                    implicitWidth: Tokens.spacing.extraLarge + Tokens.spacing.extraSmall
                    implicitHeight: implicitWidth
                    radius: Tokens.rounding.full
                    color: Qt.alpha(Colours.palette.m3primary, 0.14)

                    ProviderLogo {
                        anchors.centerIn: parent
                        provider: session.modelData.provider
                        colour: Colours.palette.m3primary
                        size: Tokens.spacing.large
                    }

                    Rectangle {
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        implicitWidth: Tokens.spacing.small + 2
                        implicitHeight: implicitWidth
                        radius: width / 2
                        border.width: 2
                        border.color: Colours.palette.m3surface
                        color: session.modelData.busy ? Colours.palette.m3success : Colours.palette.m3outline

                        SequentialAnimation on opacity {
                            running: session.modelData.busy
                            loops: Animation.Infinite
                            Anim {
                                to: 0.35
                                type: Anim.StandardSmall
                            }
                            Anim {
                                to: 1
                                type: Anim.StandardSmall
                            }
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0

                    StyledText {
                        Layout.fillWidth: true
                        text: session.folder + (session.modelData.branch ? " · " + session.modelData.branch : "")
                        font: Tokens.font.label.large
                        elide: Text.ElideRight
                    }

                    StyledText {
                        Layout.fillWidth: true
                        text: [session.account ? AiUsage.names(session.account).label : "", session.modelData.model ?? "", session.modelData.busy ? Tr.tr("working") : Tr.tr("waiting for you")].filter(Boolean).join(" · ")
                        font: Tokens.font.label.small
                        color: Colours.palette.m3onSurfaceVariant
                        elide: Text.ElideRight
                    }
                }

                ColumnLayout {
                    spacing: 0

                    StyledText {
                        Layout.alignment: Qt.AlignRight
                        text: Format.money(session.modelData.cost)
                        font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
                    }

                    StyledText {
                        Layout.alignment: Qt.AlignRight
                        text: Format.tokens(session.modelData.tokens) + " · " + Format.age(session.modelData.startedAt, root.now)
                        font: Tokens.font.label.small
                        color: Colours.palette.m3onSurfaceVariant
                    }
                }

                MaterialIcon {
                    text: "north_east"
                    opacity: session.window ? 1 : 0.3
                    color: Colours.palette.m3onSurfaceVariant
                    fontStyle: Tokens.font.icon.small
                }
            }
        }
    }
}
