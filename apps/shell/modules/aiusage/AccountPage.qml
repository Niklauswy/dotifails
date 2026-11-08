pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.services
import "Format.js" as Format

// One account: notices, identity, its limits, billing rows when the provider reports them, cost,
// running sessions and links.
ColumnLayout {
    id: root

    required property var account
    property real now: Date.now()

    signal limitRequested(int index)
    signal costRequested
    signal diskRequested

    readonly property var who: AiUsage.names(account)
    readonly property var service: AiUsage.status[account.provider]
    readonly property bool incident: AiUsage.settings.status && !!service && ["minor", "major", "critical"].includes(service.indicator)
    readonly property var day: account.usage?.["30d"]
    readonly property real today: day?.series?.[account.id]?.cost?.[(day?.points ?? 1) - 1] ?? 0
    readonly property var weekly: (account.limits ?? []).find(l => l.id === "weekly")
    readonly property var links: ({
            claude: ["https://claude.ai/settings/usage", "claude.ai/settings/usage"],
            codex: ["https://chatgpt.com/codex/settings/usage", "chatgpt.com/codex/settings/usage"],
            opencode: ["https://opencode.ai/auth", "opencode.ai"]
        })

    function open(url: string): void {
        Quickshell.execDetached(["xdg-open", url]);
    }

    function summary(): string {
        const parts = (account.limits ?? []).map(l => `${AiUsage.limitTitle(l)} ${Math.round(l.usedPercent)}%`);
        return `${account.providerName} · ${who.label}: ${parts.join(" · ")} · 30d ${Format.money(day?.totals?.cost ?? 0)}`;
    }

    spacing: Tokens.spacing.small

    Banner {
        visible: root.incident
        icon: "warning"
        tone: Colours.palette.m3tertiary
        title: root.service?.description ?? ""
        body: root.service?.url ? root.service.url.replace("https://", "") : ""
        details: (root.service?.components ?? []).map(c => ({
                    name: c.name,
                    value: c.status === "operational" ? Tr.tr("Operational") : c.status.replace(/_/g, " "),
                    colour: c.status === "operational" ? Colours.palette.m3success : Colours.palette.m3tertiary
                }))
    }

    Banner {
        visible: !!root.account.error && root.account.error.kind !== "expired"
        icon: "error"
        tone: Colours.palette.m3error
        title: root.account.error?.kind === "auth" || root.account.error?.kind === "scope" ? Tr.tr("Could not read this account: sign in again") : Tr.tr("Could not refresh this account")
        body: root.account.source === "statusline" ? Tr.tr("Showing the limits Claude Code reported last.") : ""
        command: root.account.error?.command ?? ""
    }

    Banner {
        // Claude Code renews its token only while it runs in that home: a closed Orca profile stops updating.
        visible: !!root.account.session && root.account.session.renewable && root.account.session.expired && AiUsage.isStale(root.account)
        icon: "key"
        tone: Colours.palette.m3tertiary
        title: Tr.tr("Waiting for the sign-in to renew")
        body: Tr.tr("Claude Code renews it only while it runs with this account. Open it once (in Orca, the profile) to update these limits.")
        command: "claude"
    }

    Banner {
        visible: !!root.account.session && !root.account.session.renewable && (root.account.session.expired || (!!root.account.session.expiresAt && root.account.session.expiresAt - root.now / 1000 < 86400))
        icon: "key"
        tone: Colours.palette.m3tertiary
        title: root.account.session?.expired ? Tr.tr("The sign-in has expired") : Tr.tr("The sign-in expires %1").arg(Qt.formatDateTime(new Date((root.account.session?.expiresAt ?? 0) * 1000), "ddd hh:mm"))
        body: Tr.tr("Open it once so it renews its session.")
        command: root.account.provider === "opencode" ? "opencode auth login" : root.account.provider === "codex" ? "codex login" : "claude"
    }

    Banner {
        visible: AiUsage.settings.upcoming && !!root.weekly?.resetsAt && root.weekly.usedPercent < 100 && root.weekly.resetsAt - root.now / 1000 < 86400 && root.weekly.resetsAt > root.now / 1000
        icon: "schedule"
        tone: Colours.palette.m3primary
        title: Tr.tr("Your weekly limit resets in %1").arg(Format.countdown(root.weekly?.resetsAt, root.now))
        body: Tr.tr("%1% is still unused; what you do not use is lost.").arg(Math.round(100 - (root.weekly?.usedPercent ?? 0)))
    }

    // Identity
    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: Tokens.spacing.small
        Layout.leftMargin: Tokens.padding.small
        Layout.rightMargin: Tokens.padding.small
        spacing: Tokens.spacing.medium

        StyledRect {
            implicitWidth: Tokens.spacing.extraLarge + Tokens.spacing.medium
            implicitHeight: implicitWidth
            radius: Tokens.rounding.full
            color: Qt.alpha(Colours.palette.m3primary, 0.16)

            ProviderLogo {
                anchors.centerIn: parent
                provider: root.account.provider
                colour: Colours.palette.m3primary
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0

            StyledText {
                text: root.account.providerName
                font: Tokens.font.title.medium
            }

            StyledText {
                Layout.fillWidth: true
                text: {
                    const age = Format.age(root.account.updatedAt, root.now);
                    const when = AiUsage.isStale(root.account) ? Tr.tr("data from %1 ago").arg(age) : age ? Tr.tr("updated %1 ago").arg(age) : Tr.tr("updated just now");
                    return [root.who.email || root.who.label, when].filter(Boolean).join(" · ");
                }
                font: Tokens.font.body.small
                color: AiUsage.isStale(root.account) ? Colours.palette.m3tertiary : Colours.palette.m3onSurfaceVariant
                elide: Text.ElideMiddle
            }
        }

        Chip {
            visible: !!root.account.plan
            text: root.account.plan ?? ""
        }
    }

    Divider {}

    StyledText {
        visible: !(root.account.limits?.length)
        Layout.fillWidth: true
        Layout.margins: Tokens.padding.small
        wrapMode: Text.WordWrap
        text: root.account.reason === "subscription" ? Tr.tr("No OpenCode Go subscription or sign-in yet; this is your local history.") : root.account.reason === "statusline" ? Tr.tr("Limits appear after Claude Code refreshes its status line once.") : root.account.reason === "cli" ? Tr.tr("Codex CLI not found in PATH.") : root.account.reason === "history" ? Tr.tr("This account is not signed in; only its usage history is shown.") : Tr.tr("No limits reported yet.")
        font: Tokens.font.body.small
        color: Colours.palette.m3onSurfaceVariant
    }

    Repeater {
        model: root.account.limits ?? []

        LimitBlock {
            required property var modelData
            required property int index

            limit: modelData
            now: root.now
            onClicked: root.limitRequested(index)
        }
    }

    // Billing and credits, only what the provider reports.
    ColumnLayout {
        Layout.fillWidth: true
        visible: AiUsage.settings.billing && (!!root.account.extra || !!root.account.cloud || root.account.credits !== null && root.account.credits !== undefined || (root.account.resetCredits?.available ?? 0) > 0 || !!root.account.renewsAt)
        spacing: 0

        Divider {}

        LimitBlock {
            visible: !!root.account.extra
            clickable: false
            limit: ({
                    id: "extra",
                    label: Tr.tr("Extra usage"),
                    usedPercent: root.account.extra ? 100 * root.account.extra.spent / Math.max(0.01, root.account.extra.cap) : 0,
                    resetsAt: root.account.extra?.resetsAt ?? null,
                    windowMinutes: 43200
                })
            now: root.now
        }

        MenuRow {
            visible: !!root.account.extra
            icon: "payments"
            text: Tr.tr("%1 of %2 this month").arg(Format.money(root.account.extra?.spent ?? 0)).arg(Format.money(root.account.extra?.cap ?? 0))
            enabled: false
        }

        MenuRow {
            visible: !!root.account.cloud
            icon: "cloud"
            text: Tr.tr("Cloud session credits")
            detail: root.account.cloud ? (root.account.cloud.expired ? Tr.tr("expired") : Format.money(root.account.cloud.remaining)) : ""
            enabled: false
        }

        MenuRow {
            visible: root.account.credits !== null && root.account.credits !== undefined
            icon: "toll"
            text: Tr.tr("Credits")
            detail: String(root.account.credits ?? "")
            trailing: "open_in_new"
            onClicked: root.open(root.links[root.account.provider][0])
        }

        MenuRow {
            visible: (root.account.resetCredits?.available ?? 0) > 0
            icon: "confirmation_number"
            // TRANSLATORS: %1 = number of saved limit resets
            text: Tr.tr("%1 saved resets").arg(root.account.resetCredits?.available ?? 0)
            detail: (root.account.resetCredits?.credits ?? []).filter(c => c.expiresAt).map(c => Tr.tr("expires in %1").arg(Format.countdown(c.expiresAt, root.now))).join(" · ")
            trailing: "open_in_new"
            onClicked: root.open(root.links[root.account.provider][0])
        }

        MenuRow {
            visible: !!root.account.renewsAt
            icon: "event_repeat"
            text: Tr.tr("Plan renews")
            detail: root.account.renewsAt ? Qt.formatDate(new Date(root.account.renewsAt * 1000), "d MMM") : ""
            enabled: false
        }
    }

    Divider {}

    // Cost summary
    Item {
        Layout.fillWidth: true
        implicitHeight: costColumn.implicitHeight + Tokens.padding.medium * 2

        StateLayer {
            radius: Tokens.rounding.large
            color: Colours.palette.m3onSurface
            onClicked: root.costRequested()
        }

        ColumnLayout {
            id: costColumn

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: Tokens.padding.small
            spacing: Tokens.spacing.extraSmall

            RowLayout {
                Layout.fillWidth: true

                StyledText {
                    Layout.fillWidth: true
                    text: Tr.tr("Cost")
                    font: Tokens.font.title.small
                }

                MaterialIcon {
                    text: "chevron_right"
                    color: Colours.palette.m3onSurfaceVariant
                    fontStyle: Tokens.font.icon.small
                }
            }

            RowLayout {
                Layout.fillWidth: true

                StyledText {
                    Layout.fillWidth: true
                    text: Tr.tr("Today")
                    font: Tokens.font.body.small
                    color: Colours.palette.m3onSurfaceVariant
                }

                StyledText {
                    text: Format.tokens(root.day?.series?.[root.account.id]?.tokens?.[(root.day?.points ?? 1) - 1] ?? 0) + " " + Tr.tr("tokens")
                    font: Tokens.font.body.small
                    color: Colours.palette.m3onSurfaceVariant
                }

                StyledText {
                    Layout.minimumWidth: Tokens.spacing.extraExtraLarge + Tokens.spacing.medium
                    horizontalAlignment: Text.AlignRight
                    text: Format.money(root.today)
                    font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
                }
            }

            RowLayout {
                Layout.fillWidth: true

                StyledText {
                    Layout.fillWidth: true
                    text: Tr.tr("Last 30 days")
                    font: Tokens.font.body.small
                    color: Colours.palette.m3onSurfaceVariant
                }

                StyledText {
                    text: Format.tokens(root.day?.totals?.processed ?? 0) + " " + Tr.tr("tokens")
                    font: Tokens.font.body.small
                    color: Colours.palette.m3onSurfaceVariant
                }

                StyledText {
                    Layout.minimumWidth: Tokens.spacing.extraExtraLarge + Tokens.spacing.medium
                    horizontalAlignment: Text.AlignRight
                    text: Format.money(root.day?.totals?.cost ?? 0)
                    font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
                }
            }

            // Last two weeks, newest brightest.
            Row {
                id: spark

                readonly property var values: (root.day?.series?.[root.account.id]?.cost ?? []).slice(-14)
                readonly property real peak: Math.max(0.0001, ...values)

                Layout.fillWidth: true
                Layout.topMargin: Tokens.spacing.small
                Layout.preferredHeight: Tokens.spacing.extraLarge
                spacing: Tokens.padding.extraSmall / 2

                Repeater {
                    model: spark.values

                    StyledRect {
                        required property real modelData
                        required property int index

                        y: spark.height - height
                        width: (spark.width - spark.spacing * 13) / 14
                        height: Math.max(2, spark.height * modelData / spark.peak)
                        radius: Tokens.rounding.extraSmall
                        color: index === spark.values.length - 1 ? Colours.palette.m3primary : Qt.alpha(Colours.palette.m3primary, 0.45)
                    }
                }
            }
        }
    }

    Divider {
        visible: sessions.visible
    }

    SessionRows {
        id: sessions

        Layout.topMargin: Tokens.spacing.small
        // Its own sessions; one whose account is unknown shows under every account of its provider.
        agents: AiUsage.visibleAgents.filter(a => a.provider === root.account.provider && (!a.accountId || a.accountId === root.account.id))
        now: root.now
    }

    Divider {}

    MenuRow {
        icon: "hard_drive"
        text: Tr.tr("Disk space")
        detail: root.account.disk ? Format.bytes(root.account.disk.total) + " · " + root.account.disk.root : ""
        trailing: "chevron_right"
        visible: !!root.account.disk
        onClicked: root.diskRequested()
    }

    MenuRow {
        icon: "monitoring"
        text: Tr.tr("Usage dashboard")
        detail: root.links[root.account.provider]?.[1] ?? ""
        trailing: "open_in_new"
        onClicked: root.open(root.links[root.account.provider][0])
    }

    MenuRow {
        visible: AiUsage.settings.status && !!root.service?.url
        icon: "bigtop_updates"
        text: Tr.tr("Service status")
        dot: root.incident ? Colours.palette.m3tertiary : root.service?.indicator === "none" ? Colours.palette.m3success : Colours.palette.m3outline
        detail: root.incident ? Tr.tr("Incident") : root.service?.indicator === "none" ? Tr.tr("Operational") : Tr.tr("Unknown")
        trailing: "open_in_new"
        onClicked: root.open(root.service.url)
    }

    MenuRow {
        icon: "ios_share"
        text: Tr.tr("Copy summary")
        onClicked: Quickshell.clipboardText = root.summary()
    }
}
