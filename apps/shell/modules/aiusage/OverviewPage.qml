pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services
import "Format.js" as Format

// Every visible account at a glance: spend of today and 30 days, running sessions, then one row
// per account grouped by provider (two bars, or the tightest one in compact mode).
ColumnLayout {
    id: root

    property real now: Date.now()

    signal accountRequested(string provider, string id)
    signal addRequested
    signal settingsRequested

    readonly property var accounts: AiUsage.visibleAccounts
    readonly property real today: accounts.reduce((sum, a) => {
        const day = a.usage?.["30d"];
        return sum + (day?.series?.[a.id]?.cost?.[(day?.points ?? 1) - 1] ?? 0);
    }, 0)
    readonly property real month: accounts.reduce((sum, a) => sum + (a.usage?.["30d"]?.totals?.cost ?? 0), 0)

    spacing: Tokens.spacing.small

    RowLayout {
        Layout.fillWidth: true
        Layout.margins: Tokens.padding.small
        spacing: Tokens.spacing.extraLarge

        ColumnLayout {
            spacing: 0

            StyledText {
                text: Tr.tr("Today")
                font: Tokens.font.label.small
                color: Colours.palette.m3onSurfaceVariant
            }

            StyledText {
                text: Format.money(root.today)
                font: Tokens.font.headline.builders.medium.weight(Font.DemiBold).build()
            }
        }

        ColumnLayout {
            Layout.alignment: Qt.AlignBottom
            spacing: 0

            StyledText {
                text: Tr.tr("30 days")
                font: Tokens.font.label.small
                color: Colours.palette.m3onSurfaceVariant
            }

            StyledText {
                text: Format.money(root.month)
                font: Tokens.font.title.builders.large.weight(Font.DemiBold).build()
            }
        }

        StyledText {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignBottom
            horizontalAlignment: Text.AlignRight
            // TRANSLATORS: %1 = number of accounts, %2 = number of providers
            text: Tr.tr("%1 accounts · %2 providers").arg(root.accounts.length).arg(AiUsage.providers.length) + "\n" + Tr.tr("estimate at API prices")
            font: Tokens.font.label.small
            color: Colours.palette.m3onSurfaceVariant
        }
    }

    Divider {
        visible: sessions.visible
    }

    SessionRows {
        id: sessions

        Layout.topMargin: Tokens.spacing.small
        agents: AiUsage.visibleAgents
        now: root.now
    }

    Divider {}

    StyledText {
        visible: root.accounts.length === 0
        Layout.fillWidth: true
        Layout.margins: Tokens.padding.large
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: Tr.tr("No accounts to show. Turn some on in Settings.")
        color: Colours.palette.m3onSurfaceVariant
    }

    Repeater {
        model: AiUsage.providers

        ColumnLayout {
            id: group

            required property string modelData
            readonly property var service: AiUsage.status[modelData]
            readonly property bool incident: AiUsage.settings.status && !!service && ["minor", "major", "critical"].includes(service.indicator)

            Layout.fillWidth: true
            spacing: 0

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Tokens.padding.small
                Layout.rightMargin: Tokens.padding.small
                Layout.topMargin: Tokens.spacing.small
                spacing: Tokens.spacing.small

                ProviderLogo {
                    provider: group.modelData
                    colour: Colours.palette.m3onSurfaceVariant
                    size: Tokens.spacing.medium
                }

                StyledText {
                    Layout.fillWidth: true
                    text: AiUsage.providerName(group.modelData).toUpperCase()
                    font: Tokens.font.label.builders.small.weight(Font.DemiBold).build()
                    color: Colours.palette.m3onSurfaceVariant
                }

                Rectangle {
                    visible: AiUsage.settings.status && !!group.service?.url
                    implicitWidth: Tokens.spacing.small
                    implicitHeight: implicitWidth
                    radius: width / 2
                    color: group.incident ? Colours.palette.m3tertiary : Colours.palette.m3success
                }
            }

            Repeater {
                model: AiUsage.providerAccounts(group.modelData)

                Item {
                    id: row

                    required property var modelData
                    readonly property var who: AiUsage.names(modelData)
                    readonly property var limits: {
                        const all = modelData.limits ?? [];
                        if (!AiUsage.settings.compact)
                            return all.slice(0, 2);
                        return all.length ? [all.reduce((m, l) => l.usedPercent > m.usedPercent ? l : m, all[0])] : [];
                    }

                    Layout.fillWidth: true
                    implicitHeight: line.implicitHeight + (AiUsage.settings.compact ? Tokens.padding.small : Tokens.padding.medium) * 2

                    StateLayer {
                        radius: Tokens.rounding.large
                        color: Colours.palette.m3onSurface
                        onClicked: root.accountRequested(row.modelData.provider, row.modelData.id)
                    }

                    RowLayout {
                        id: line

                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: Tokens.padding.small
                        anchors.rightMargin: Tokens.padding.small
                        spacing: Tokens.spacing.medium

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Tokens.spacing.extraSmall

                            RowLayout {
                                spacing: Tokens.spacing.small

                                StyledText {
                                    text: row.who.label
                                    font: Tokens.font.label.large
                                    color: AiUsage.isStale(row.modelData) ? Colours.palette.m3tertiary : Colours.palette.m3onSurface
                                }

                                StyledText {
                                    visible: !!row.modelData.plan
                                    text: row.modelData.plan ?? ""
                                    font: Tokens.font.label.small
                                    color: Colours.palette.m3onSurfaceVariant
                                }
                            }

                            StyledText {
                                visible: row.limits.length === 0
                                text: row.modelData.reason === "subscription" ? Tr.tr("History only") : Tr.tr("No limits yet")
                                font: Tokens.font.label.small
                                color: Colours.palette.m3onSurfaceVariant
                            }

                            Repeater {
                                model: row.limits

                                RowLayout {
                                    id: bar

                                    required property var modelData
                                    readonly property real shown: AiUsage.settings.showUsed ? modelData.usedPercent : 100 - modelData.usedPercent

                                    Layout.fillWidth: true
                                    spacing: Tokens.spacing.small

                                    StyledText {
                                        Layout.preferredWidth: Tokens.spacing.extraExtraLarge + Tokens.spacing.medium
                                        text: AiUsage.limitTitle(bar.modelData)
                                        font: Tokens.font.label.small
                                        color: Colours.palette.m3onSurfaceVariant
                                        elide: Text.ElideRight
                                    }

                                    StyledRect {
                                        Layout.fillWidth: true
                                        implicitHeight: Tokens.sizes.aiUsage.typeBarHeight
                                        radius: Tokens.rounding.full
                                        color: Qt.alpha(Colours.palette.m3onSurface, 0.09)

                                        StyledRect {
                                            anchors.left: parent.left
                                            anchors.top: parent.top
                                            anchors.bottom: parent.bottom
                                            width: parent.width * Math.max(0, Math.min(1, bar.shown / 100))
                                            radius: Tokens.rounding.full
                                            color: AiUsage.severityColour(bar.modelData.usedPercent)
                                        }
                                    }

                                    StyledText {
                                        Layout.preferredWidth: Tokens.spacing.extraLarge + Tokens.spacing.small
                                        horizontalAlignment: Text.AlignRight
                                        text: Math.round(bar.shown) + "%"
                                        font: Tokens.font.label.builders.small.weight(Font.DemiBold).build()
                                        color: bar.modelData.usedPercent >= 90 ? Colours.palette.m3error : Colours.palette.m3onSurface
                                    }

                                    StyledText {
                                        Layout.preferredWidth: Tokens.spacing.extraExtraLarge + Tokens.spacing.large
                                        horizontalAlignment: Text.AlignRight
                                        text: bar.modelData.resetsAt ? (AiUsage.settings.absoluteResets ? Qt.formatDateTime(new Date(bar.modelData.resetsAt * 1000), "ddd hh:mm") : Format.countdown(bar.modelData.resetsAt, root.now)) : "—"
                                        font: Tokens.font.label.small
                                        color: Colours.palette.m3onSurfaceVariant
                                    }
                                }
                            }
                        }

                        MaterialIcon {
                            text: "chevron_right"
                            color: Colours.palette.m3onSurfaceVariant
                            fontStyle: Tokens.font.icon.small
                        }
                    }
                }
            }
        }
    }

    Divider {
        Layout.topMargin: Tokens.spacing.small
    }

    MenuRow {
        icon: "person_add"
        text: Tr.tr("Add account…")
        onClicked: root.addRequested()
    }

    MenuRow {
        icon: "tune"
        text: Tr.tr("Settings")
        trailing: "chevron_right"
        onClicked: root.settingsRequested()
    }
}
