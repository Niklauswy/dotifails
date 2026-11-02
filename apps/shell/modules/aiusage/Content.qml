pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.components.misc
import qs.services

// AI usage panel: Overview plus one tab per provider; in a provider, chips pick the account.
// Pages: main, limit history, cost, disk and settings; Esc goes back before it closes.
Item {
    id: root

    required property real maxHeight

    property real now: Date.now()
    property string provider: "overview"
    property string page: "main"
    property int limitIndex: 0
    property bool adding
    // Selected account per provider.
    property var selectedIds: ({})

    readonly property var tabs: ["overview"].concat(AiUsage.providers)
    readonly property var providerAccounts: provider === "overview" ? [] : AiUsage.providerAccounts(provider)
    readonly property var selected: providerAccounts.find(a => a.id === selectedIds[provider]) ?? providerAccounts[0] ?? null

    signal closeRequested
    signal interacted

    implicitWidth: Tokens.sizes.aiUsage.width
    implicitHeight: Math.min(root.maxHeight, header.implicitHeight + tabBar.implicitHeight + body.implicitHeight + Tokens.padding.large * 2 + Tokens.spacing.medium * 2)

    function choose(provider: string): void {
        root.provider = AiUsage.providers.includes(provider) ? provider : "overview";
        page = "main";
        adding = false;
    }

    function chooseAccount(id: string): void {
        const next = Object.assign({}, selectedIds);
        next[provider] = id;
        selectedIds = next;
        page = "main";
    }

    function back(): bool {
        if (adding) {
            adding = false;
            return true;
        }
        if (page !== "main") {
            page = "main";
            return true;
        }
        return false;
    }

    function addAccount(provider: string): void {
        adding = false;
        AiUsage.addAccount(provider);
        root.closeRequested();
    }

    // Pages differ in height and scroll, so each one opens at its top.
    onPageChanged: scroller.contentY = 0
    onProviderChanged: scroller.contentY = 0
    onAddingChanged: scroller.contentY = 0

    onTabsChanged: {
        if (!tabs.includes(provider))
            provider = "overview";
    }

    focus: true
    Keys.onPressed: event => {
        const ctrl = event.modifiers & Qt.ControlModifier;
        const alt = event.modifiers & Qt.AltModifier;
        if (alt && event.key >= Qt.Key_1 && event.key <= Qt.Key_9) {
            const id = root.tabs[event.key - Qt.Key_1];
            if (id)
                root.choose(id);
        } else if (ctrl && (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab)) {
            const list = root.providerAccounts;
            if (list.length > 1) {
                const step = event.key === Qt.Key_Backtab || event.modifiers & Qt.ShiftModifier ? -1 : 1;
                const index = Math.max(0, list.indexOf(root.selected));
                root.chooseAccount(list[(index + step + list.length) % list.length].id);
            }
        } else if (ctrl && event.key === Qt.Key_R) {
            AiUsage.refresh();
        } else if (event.key === Qt.Key_Escape) {
            if (!root.back())
                root.closeRequested();
        } else {
            return;
        }
        event.accepted = true;
    }

    Ref {
        service: AiUsage
    }

    Timer {
        interval: 30000
        running: true
        repeat: true
        onTriggered: root.now = Date.now()
    }

    Connections {
        function onSnapshotChanged(): void {
            root.now = Date.now();
        }

        target: AiUsage
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.medium

        RowLayout {
            id: header

            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small
            spacing: Tokens.spacing.small

            StyledText {
                Layout.fillWidth: true
                text: Tr.tr("AI usage")
                font: Tokens.font.title.medium
            }

            StyledText {
                readonly property bool troubled: AiUsage.visibleAccounts.some(a => !!a.error && a.error.kind !== "expired")

                text: AiUsage.loading ? Tr.tr("Updating…") : troubled ? Tr.tr("An account could not be read") : AiUsage.snapshot ? Tr.tr("Updated %1").arg(Qt.formatTime(new Date(AiUsage.snapshot.generatedAt * 1000), "hh:mm")) + (AiUsage.interval === 0 ? " · " + Tr.tr("manual") : AiUsage.settings.refresh === "adaptive" ? " · " + (AiUsage.anyBusy ? Tr.tr("agent working, every minute") : Tr.tr("idle, every %1 min").arg(Math.round(Tokens.sizes.aiUsage.idleInterval / 60000))) : "") : Tr.tr("Reading session logs…")
                font: Tokens.font.label.small
                color: troubled ? Colours.palette.m3tertiary : Colours.palette.m3onSurfaceVariant
            }

            IconButton {
                icon: AiUsage.loading ? "hourglass_top" : "refresh"
                type: IconButton.Text
                disabled: AiUsage.loading
                onClicked: AiUsage.refresh()
            }

            IconButton {
                icon: "settings"
                type: root.page === "settings" ? IconButton.Tonal : IconButton.Text
                onClicked: root.page = root.page === "settings" ? "main" : "settings"
            }
        }

        ProviderTabs {
            id: tabBar

            visible: root.page !== "settings"
            current: root.provider
            onSelected: provider => root.choose(provider)
        }

        Flickable {
            id: scroller

            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: body.implicitHeight
            interactive: contentHeight > height
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            ColumnLayout {
                id: body

                width: parent.width
                spacing: Tokens.spacing.small

                // Provider picker for "Add account…" from the overview.
                Flow {
                    Layout.fillWidth: true
                    visible: root.adding
                    spacing: Tokens.spacing.small

                    Repeater {
                        model: ["claude", "codex", "opencode"]

                        Chip {
                            id: choice

                            required property string modelData

                            icon: "add"
                            text: AiUsage.providerName(modelData)

                            StateLayer {
                                radius: Tokens.rounding.full
                                color: Colours.palette.m3primary
                                onClicked: root.addAccount(choice.modelData)
                            }
                        }
                    }
                }

                AccountChips {
                    visible: root.provider !== "overview" && root.page === "main"
                    provider: root.provider === "overview" ? "" : root.provider
                    current: root.selected?.id ?? ""
                    onSelected: id => root.chooseAccount(id)
                    onAddRequested: root.addAccount(root.provider)
                }

                Loader {
                    id: pageLoader

                    Layout.fillWidth: true
                    sourceComponent: {
                        if (root.page === "settings")
                            return settingsPage;
                        if (root.provider === "overview" || !root.selected)
                            return overviewPage;
                        if (root.page === "limit" && root.selected.limits?.[root.limitIndex])
                            return limitPage;
                        if (root.page === "cost")
                            return costPage;
                        if (root.page === "disk" && root.selected.disk)
                            return diskPage;
                        return accountPage;
                    }
                }
            }
        }
    }

    // Any press counts; it is not accepted, so it still reaches the control below.
    MouseArea {
        anchors.fill: parent
        z: 1
        acceptedButtons: Qt.AllButtons
        onPressed: mouse => {
            root.interacted();
            mouse.accepted = false;
        }
    }

    Component {
        id: overviewPage

        OverviewPage {
            now: root.now
            onAccountRequested: (provider, id) => {
                root.choose(provider);
                root.chooseAccount(id);
            }
            onAddRequested: root.adding = !root.adding
            onSettingsRequested: root.page = "settings"
        }
    }

    Component {
        id: accountPage

        AccountPage {
            account: root.selected
            now: root.now
            onLimitRequested: index => {
                root.limitIndex = index;
                root.page = "limit";
            }
            onCostRequested: root.page = "cost"
            onDiskRequested: root.page = "disk"
        }
    }

    Component {
        id: limitPage

        LimitHistoryPage {
            account: root.selected
            limit: root.selected.limits[root.limitIndex]
            now: root.now
            onBackRequested: root.page = "main"
        }
    }

    Component {
        id: costPage

        CostPage {
            account: root.selected
            now: root.now
            onBackRequested: root.page = "main"
        }
    }

    Component {
        id: diskPage

        DiskPage {
            account: root.selected
            onBackRequested: root.page = "main"
        }
    }

    Component {
        id: settingsPage

        SettingsPage {
            onBackRequested: root.page = "main"
        }
    }
}
