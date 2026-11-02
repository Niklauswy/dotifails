pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services

// One tab per provider with a visible account, after Overview: logo, name, a meter of its tightest
// limit and a dot for an incident or a spent limit. Alt+1…9 follow this order.
StyledRect {
    id: root

    property string current: "overview"

    signal selected(string provider)

    readonly property var tabs: ["overview"].concat(AiUsage.providers)

    Layout.fillWidth: true
    implicitHeight: row.implicitHeight + Tokens.padding.extraSmall * 2
    radius: Tokens.rounding.extraLarge
    color: Colours.tPalette.m3surfaceContainer

    function providerName(provider: string): string {
        return provider === "claude" ? "Claude" : provider === "codex" ? "Codex" : provider === "opencode" ? "OpenCode" : provider;
    }

    RowLayout {
        id: row

        anchors.fill: parent
        anchors.margins: Tokens.padding.extraSmall
        spacing: Tokens.spacing.extraSmall

        Repeater {
            model: root.tabs

            StyledRect {
                id: tab

                required property string modelData
                required property int index
                readonly property bool active: root.current === modelData
                readonly property bool overview: modelData === "overview"
                readonly property var tight: overview ? null : AiUsage.tightestOf(modelData)
                readonly property var service: AiUsage.status[modelData]
                readonly property bool incident: AiUsage.settings.status && !!service && ["minor", "major", "critical"].includes(service.indicator)
                readonly property color foreground: active ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant

                Layout.fillWidth: true
                Layout.preferredWidth: 1
                implicitHeight: content.implicitHeight + Tokens.padding.small * 2
                radius: Tokens.rounding.large
                color: active ? Colours.palette.m3secondaryContainer : "transparent"

                Behavior on color {
                    CAnim {}
                }

                StateLayer {
                    radius: tab.radius
                    color: tab.foreground
                    onClicked: root.selected(tab.modelData)
                }

                StyledText {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.margins: Tokens.padding.small
                    visible: tab.index < 9
                    text: tab.index + 1
                    font: Tokens.font.label.small
                    color: Qt.alpha(tab.foreground, 0.5)
                }

                Rectangle {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: Tokens.padding.small
                    visible: tab.incident || (tab.tight?.remaining ?? 100) <= Tokens.sizes.aiUsage.alertThreshold
                    implicitWidth: Tokens.spacing.small
                    implicitHeight: implicitWidth
                    radius: width / 2
                    color: tab.incident ? Colours.palette.m3tertiary : Colours.palette.m3error
                }

                ColumnLayout {
                    id: content

                    anchors.centerIn: parent
                    spacing: Tokens.spacing.extraSmall

                    ProviderLogo {
                        Layout.alignment: Qt.AlignHCenter
                        visible: !tab.overview
                        provider: tab.modelData
                        colour: tab.foreground
                    }

                    MaterialIcon {
                        Layout.alignment: Qt.AlignHCenter
                        visible: tab.overview
                        text: "space_dashboard"
                        color: tab.foreground
                        fontStyle: Tokens.font.icon.medium
                    }

                    StyledText {
                        Layout.alignment: Qt.AlignHCenter
                        text: tab.overview ? Tr.tr("Overview") : root.providerName(tab.modelData)
                        font: Tokens.font.label.builders.medium.weight(tab.active ? Font.DemiBold : Font.Medium).build()
                        color: tab.foreground
                    }

                    StyledRect {
                        Layout.alignment: Qt.AlignHCenter
                        implicitWidth: Tokens.spacing.extraLarge + Tokens.spacing.large
                        implicitHeight: Tokens.sizes.aiUsage.modelBarHeight
                        radius: Tokens.rounding.full
                        opacity: tab.tight ? 1 : 0
                        color: Qt.alpha(tab.foreground, 0.2)

                        StyledRect {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: parent.width * Math.max(0, (tab.tight?.remaining ?? 0) / 100)
                            radius: Tokens.rounding.full
                            color: AiUsage.severityColour(100 - (tab.tight?.remaining ?? 100))
                        }
                    }
                }
            }
        }
    }
}
