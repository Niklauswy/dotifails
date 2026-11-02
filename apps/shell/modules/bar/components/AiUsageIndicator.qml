import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.aiusage as AiUsagePanel

// One AI limit in the bar, chosen by AiUsage.indicator (the focused app's provider, the tightest,
// or a chosen account), in the style set in the panel's settings. Dimmed with a clock when its
// data is old or could not be read; a dot marks a service incident. Opens the AI usage panel.
Item {
    id: root

    required property ScreenState screenState

    readonly property var target: AiUsage.indicator
    readonly property var account: target?.account ?? null
    readonly property string style: AiUsage.settings.indicatorStyle
    readonly property var session: (account?.limits ?? []).find(l => l.id === "session") ?? null
    readonly property var weekly: (account?.limits ?? []).find(l => l.id === "weekly") ?? null
    readonly property bool showUsed: AiUsage.settings.showUsed
    readonly property real used: target?.limit.usedPercent ?? 0
    readonly property bool stale: AiUsage.isStale(account)
    readonly property var service: account ? AiUsage.status[account.provider] : null
    readonly property bool incident: AiUsage.settings.status && !!service && ["minor", "major", "critical"].includes(service.indicator)
    readonly property color colour: AiUsage.severityColour(used)

    function shown(limit: var): int {
        if (!limit)
            return 0;
        return Math.round(showUsed ? limit.usedPercent : 100 - limit.usedPercent);
    }

    visible: !!target
    implicitWidth: Tokens.sizes.bar.innerWidth
    implicitHeight: layout.implicitHeight + Tokens.padding.small
    opacity: stale ? 0.45 : 1

    StateLayer {
        radius: Tokens.rounding.full
        onClicked: root.screenState.aiUsage = !root.screenState.aiUsage
    }

    ColumnLayout {
        id: layout

        anchors.centerIn: parent
        spacing: Tokens.spacing.extraSmall / 2

        Item {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: Tokens.sizes.aiUsage.barIndicatorSize
            implicitHeight: implicitWidth

            CircularProgress {
                anchors.fill: parent
                visible: root.style === "percent"
                implicitSize: parent.implicitWidth
                strokeWidth: Tokens.padding.extraSmall / 2
                value: root.showUsed ? root.used / 100 : 1 - root.used / 100
                fgColour: root.colour
                bgColour: Qt.alpha(root.colour, 0.2)
            }

            AiUsagePanel.ProviderLogo {
                anchors.centerIn: parent
                provider: root.account?.provider ?? ""
                colour: root.style === "percent" ? root.colour : Colours.palette.m3onSurfaceVariant
                size: root.style === "percent" ? parent.implicitWidth / 2 : parent.implicitWidth * 0.7
            }

            Rectangle {
                anchors.top: parent.top
                anchors.right: parent.right
                visible: root.incident
                implicitWidth: Tokens.spacing.small
                implicitHeight: implicitWidth
                radius: width / 2
                border.width: Tokens.padding.extraSmall / 2
                border.color: Colours.palette.m3surface
                color: Colours.palette.m3tertiary
            }

            MaterialIcon {
                anchors.bottom: parent.bottom
                anchors.right: parent.right
                anchors.rightMargin: -Tokens.spacing.extraSmall
                visible: root.stale
                text: "schedule"
                fill: 1
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.small
            }
        }

        // "meters": session and weekly as two short vertical bars of what is used (or left).
        Row {
            Layout.alignment: Qt.AlignHCenter
            visible: root.style === "meters"
            spacing: Tokens.spacing.extraSmall

            Repeater {
                model: [root.session, root.weekly].filter(l => !!l)

                StyledRect {
                    required property var modelData

                    implicitWidth: Tokens.sizes.aiUsage.typeBarHeight
                    implicitHeight: Tokens.sizes.aiUsage.barIndicatorSize
                    radius: Tokens.rounding.full
                    color: Qt.alpha(Colours.palette.m3onSurface, 0.12)

                    StyledRect {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: parent.height * root.shown(parent.modelData) / 100
                        radius: Tokens.rounding.full
                        color: AiUsage.severityColour(parent.modelData.usedPercent)
                    }
                }
            }
        }

        StyledText {
            Layout.alignment: Qt.AlignHCenter
            visible: root.style === "percent"
            text: root.shown(root.target?.limit) + "%"
            font: Tokens.font.label.builders.small.weight(Font.DemiBold).build()
            color: root.colour
        }

        StyledText {
            Layout.alignment: Qt.AlignHCenter
            visible: root.style === "stacked"
            horizontalAlignment: Text.AlignHCenter
            // TRANSLATORS: one-letter marks of the session (S) and weekly (W) limits in the bar
            text: (root.session ? Tr.tr("S %1").arg(root.shown(root.session)) : "") + (root.session && root.weekly ? "\n" : "") + (root.weekly ? Tr.tr("W %1").arg(root.shown(root.weekly)) : "")
            font: Tokens.font.label.builders.small.weight(Font.DemiBold).build()
            color: Colours.palette.m3onSurface
        }

        StyledText {
            readonly property var pace: AiUsage.pace(root.weekly ?? root.target?.limit)

            Layout.alignment: Qt.AlignHCenter
            visible: root.style === "pace"
            text: pace && !pace.early ? (pace.delta > 0 ? "+" : "") + pace.delta + "%" : "–"
            font: Tokens.font.label.builders.small.weight(Font.DemiBold).build()
            color: !pace || pace.early ? Colours.palette.m3onSurfaceVariant : pace.delta > 0 ? Colours.palette.m3error : Colours.palette.m3success
        }
    }
}
