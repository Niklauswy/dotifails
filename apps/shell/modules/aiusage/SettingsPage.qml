pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.services

// Panel settings, saved by the service in ai-usage.json: providers and the accounts shown,
// the bar indicator, what is shown, notifications and refresh.
ColumnLayout {
    id: root

    signal backRequested

    readonly property var settings: AiUsage.settings

    spacing: Tokens.spacing.small

    PageHeader {
        title: Tr.tr("AI usage settings")
        onBackRequested: root.backRequested()
    }

    Section {
        text: Tr.tr("Providers and accounts")
    }

    Repeater {
        model: ["claude", "codex", "opencode"]

        ColumnLayout {
            id: provider

            required property string modelData
            readonly property bool on: root.settings.providers?.[modelData] ?? true
            // Every account, also the hidden ones, so they can be shown again.
            readonly property var all: AiUsage.accounts.filter(a => a.provider === modelData)

            Layout.fillWidth: true
            spacing: 0

            Option {
                icon: ""
                logo: provider.modelData
                text: AiUsage.providerName(provider.modelData)
                detail: provider.all.length ? Tr.tr("%1 accounts").arg(provider.all.length) : Tr.tr("Not found on this computer")
                checked: provider.on
                onToggled: checked => AiUsage.setProvider(provider.modelData, checked)
            }

            Repeater {
                model: provider.on ? provider.all : []

                Option {
                    required property var modelData

                    Layout.leftMargin: Tokens.padding.large * 2
                    icon: "person"
                    text: modelData.label + (modelData.plan ? " · " + modelData.plan : "")
                    detail: modelData.email ?? ""
                    checked: !(root.settings.hidden ?? []).includes(modelData.id)
                    onToggled: checked => AiUsage.setHidden(modelData.id, !checked)
                }
            }
        }
    }

    Section {
        text: Tr.tr("Bar indicator")
    }

    Choice {
        text: Tr.tr("Style")
        key: "indicatorStyle"
        options: [{ value: "meters", text: Tr.tr("Bars") }, { value: "percent", text: Tr.tr("Icon + %") }, { value: "stacked", text: Tr.tr("Stacked") }, { value: "pace", text: Tr.tr("Pace") }]
    }

    Choice {
        text: Tr.tr("Follows")
        detail: Tr.tr("Focused app: the provider whose agent runs in the active window")
        key: "indicatorFollows"
        options: [{ value: "focused", text: Tr.tr("Focused app") }, { value: "tightest", text: Tr.tr("Tightest") }]
    }

    Section {
        text: Tr.tr("Show")
    }

    Option {
        text: Tr.tr("Show the used share")
        detail: Tr.tr("Off: bars and percentages show what is left")
        checked: root.settings.showUsed
        onToggled: checked => AiUsage.setSetting("showUsed", checked)
    }

    Option {
        text: Tr.tr("Exact reset time")
        detail: Tr.tr("“Thu 13:24” instead of “in 3d 20h”")
        checked: root.settings.absoluteResets
        onToggled: checked => AiUsage.setSetting("absoluteResets", checked)
    }

    Option {
        text: Tr.tr("Even-use guide")
        detail: Tr.tr("A mark on each bar and a line in the history")
        checked: root.settings.paceGuide
        onToggled: checked => AiUsage.setSetting("paceGuide", checked)
    }

    Choice {
        text: Tr.tr("Working days for the weekly pace")
        key: "workDays"
        options: [{ value: "auto", text: Tr.tr("All") }, { value: "5", text: "5" }, { value: "6", text: "6" }]
    }

    Option {
        text: Tr.tr("Extra usage, credits and billing")
        checked: root.settings.billing
        onToggled: checked => AiUsage.setSetting("billing", checked)
    }

    Option {
        text: Tr.tr("Compact overview")
        detail: Tr.tr("One bar per account: the tightest")
        checked: root.settings.compact
        onToggled: checked => AiUsage.setSetting("compact", checked)
    }

    Option {
        text: Tr.tr("Hide personal details")
        detail: Tr.tr("E-mail addresses and account names, also in notifications")
        checked: root.settings.hidePersonal
        onToggled: checked => AiUsage.setSetting("hidePersonal", checked)
    }

    Option {
        text: Tr.tr("Check service status")
        detail: "status.claude.com · status.openai.com"
        checked: root.settings.status
        onToggled: checked => AiUsage.setSetting("status", checked)
    }

    Section {
        text: Tr.tr("Notifications")
    }

    Option {
        text: Tr.tr("Limit almost spent")
        detail: Tr.tr("Once per window, at %1% left").arg(Tokens.sizes.aiUsage.alertThreshold)
        checked: root.settings.notifyLow
        onToggled: checked => AiUsage.setSetting("notifyLow", checked)
    }

    Option {
        text: Tr.tr("Limit reset")
        checked: root.settings.notifyReset
        onToggled: checked => AiUsage.setSetting("notifyReset", checked)
    }

    Option {
        text: Tr.tr("Weekly reset with quota left")
        detail: Tr.tr("24 h and 1 h before")
        checked: root.settings.upcoming
        onToggled: checked => AiUsage.setSetting("upcoming", checked)
    }

    Option {
        text: Tr.tr("Confetti on the weekly reset")
        checked: root.settings.confetti
        onToggled: checked => AiUsage.setSetting("confetti", checked)
    }

    Section {
        text: Tr.tr("Refresh")
    }

    Choice {
        text: Tr.tr("How often")
        detail: root.settings.refresh === "manual" ? Tr.tr("Notifications need refreshes to arrive") : Tr.tr("Adaptive: every minute while an agent works, every 15 min otherwise")
        key: "refresh"
        options: [{ value: "adaptive", text: Tr.tr("Adaptive") }, { value: "60000", text: Tr.tr("1 min") }, { value: "300000", text: Tr.tr("5 min") }, { value: "900000", text: Tr.tr("15 min") }, { value: "manual", text: Tr.tr("Manual") }]
    }

    component Section: StyledText {
        Layout.leftMargin: Tokens.padding.small
        Layout.topMargin: Tokens.spacing.medium
        font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
        color: Colours.palette.m3primary
    }

    component Option: Item {
        id: toggle

        property string icon
        property string logo
        property string text
        property string detail
        property bool checked

        signal toggled(bool checked)

        Layout.fillWidth: true
        implicitHeight: row.implicitHeight + Tokens.padding.small * 2

        RowLayout {
            id: row

            anchors.fill: parent
            anchors.leftMargin: Tokens.padding.small
            anchors.rightMargin: Tokens.padding.small
            spacing: Tokens.spacing.medium

            ProviderLogo {
                visible: !!toggle.logo
                provider: toggle.logo
                colour: Colours.palette.m3onSurfaceVariant
            }

            MaterialIcon {
                visible: !!toggle.icon
                text: toggle.icon
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.small
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                StyledText {
                    Layout.fillWidth: true
                    text: toggle.text
                    font: Tokens.font.body.medium
                    elide: Text.ElideRight
                }

                StyledText {
                    Layout.fillWidth: true
                    visible: !!toggle.detail
                    text: toggle.detail
                    font: Tokens.font.label.small
                    color: Colours.palette.m3onSurfaceVariant
                    elide: Text.ElideRight
                }
            }

            StyledSwitch {
                checked: toggle.checked
                onClicked: toggle.toggled(checked)
            }
        }
    }

    component Choice: ColumnLayout {
        id: choice

        property string text
        property string detail
        property string key
        property var options: []

        Layout.fillWidth: true
        Layout.leftMargin: Tokens.padding.small
        Layout.rightMargin: Tokens.padding.small
        spacing: Tokens.spacing.extraSmall

        RowLayout {
            Layout.fillWidth: true

            StyledText {
                Layout.fillWidth: true
                text: choice.text
                font: Tokens.font.body.medium
            }

            Segmented {
                current: String(root.settings[choice.key] ?? "")
                options: choice.options
                onSelected: value => AiUsage.setSetting(choice.key, value)
            }
        }

        StyledText {
            Layout.fillWidth: true
            visible: !!choice.detail
            text: choice.detail
            font: Tokens.font.label.small
            color: Colours.palette.m3onSurfaceVariant
            wrapMode: Text.WordWrap
        }
    }
}
