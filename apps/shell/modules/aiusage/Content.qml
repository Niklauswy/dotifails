pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.components.misc
import qs.services

// AI usage panel: an overview tab plus one tab per signed-in account.
Item {
    id: root

    required property real maxHeight

    property real now: Date.now()
    readonly property var selected: AiUsage.account(AiUsage.tab)

    // Overview first, then the accounts: Alt+1 … Alt+9 select them.
    readonly property var tabIds: ["overview"].concat(AiUsage.accounts.map(a => a.id))

    signal closeRequested

    implicitWidth: Tokens.sizes.aiUsage.width
    implicitHeight: Math.min(root.maxHeight, header.implicitHeight + tabs.implicitHeight + page.implicitHeight + Tokens.padding.large * 2 + Tokens.spacing.medium * 2)

    focus: true
    Keys.onPressed: event => {
        const ctrl = event.modifiers & Qt.ControlModifier;
        const alt = event.modifiers & Qt.AltModifier;
        if (alt && event.key >= Qt.Key_1 && event.key <= Qt.Key_9) {
            const id = root.tabIds[event.key - Qt.Key_1];
            if (id)
                AiUsage.tab = id;
        } else if (ctrl && (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab)) {
            const step = event.key === Qt.Key_Backtab || event.modifiers & Qt.ShiftModifier ? -1 : 1;
            const index = root.tabIds.indexOf(AiUsage.tab);
            AiUsage.tab = root.tabIds[(index + step + root.tabIds.length) % root.tabIds.length];
        } else if (ctrl && event.key === Qt.Key_R) {
            AiUsage.refresh();
        } else if (event.key === Qt.Key_Escape) {
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
            spacing: Tokens.spacing.small

            StyledRect {
                implicitWidth: Tokens.sizes.aiUsage.limitBarHeight * 1.6
                implicitHeight: implicitWidth
                radius: Tokens.rounding.full
                color: Colours.palette.m3primaryContainer

                MaterialIcon {
                    anchors.centerIn: parent
                    text: "data_usage"
                    color: Colours.palette.m3onPrimaryContainer
                    fontStyle: Tokens.font.icon.medium
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                StyledText {
                    text: Tr.tr("AI usage")
                    font: Tokens.font.title.medium
                }

                StyledText {
                    Layout.fillWidth: true
                    text: AiUsage.snapshot ? Tr.tr("Updated %1").arg(Qt.formatTime(new Date(AiUsage.snapshot.generatedAt * 1000), "hh:mm")) : Tr.tr("Reading session logs…")
                    font: Tokens.font.label.small
                    color: Colours.palette.m3onSurfaceVariant
                    elide: Text.ElideRight
                }
            }

            IconButton {
                icon: AiUsage.loading ? "hourglass_top" : "refresh"
                type: IconButton.Text
                disabled: AiUsage.loading
                onClicked: AiUsage.refresh()
            }
        }

        // Tabs share the width evenly, so any number of accounts fits.
        RowLayout {
            id: tabs

            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            Tab {
                shortcut: 1
                tabId: "overview"
                text: Tr.tr("Overview")
                icon: "dashboard"
                colour: Colours.palette.m3primary
            }

            Repeater {
                model: AiUsage.accounts

                Tab {
                    required property var modelData
                    required property int index

                    shortcut: index + 2
                    tabId: modelData.id
                    text: AiUsage.accounts.filter(a => a.provider === modelData.provider).length > 1 ? modelData.label : modelData.providerName
                    provider: modelData.provider
                    colour: AiUsage.colour(modelData.id)
                    meter: modelData.limits?.length ? 1 - modelData.limits[0].usedPercent / 100 : -1
                }
            }
        }

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: page.implicitHeight
            interactive: contentHeight > height
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            Loader {
                id: page

                width: parent.width
                sourceComponent: root.selected ? accountPage : overviewPage
            }
        }
    }

    Component {
        id: overviewPage

        OverviewPage {
            now: root.now
        }
    }

    Component {
        id: accountPage

        AccountPage {
            account: root.selected
            now: root.now
        }
    }

    component Tab: StyledRect {
        id: tab

        property int shortcut
        property string tabId
        property string text
        property string icon
        property string provider
        property color colour
        // Remaining share of the first limit, or -1 for none.
        property real meter: -1
        readonly property bool active: AiUsage.tab === tabId
        readonly property color foreground: active ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurface

        Layout.fillWidth: true
        Layout.preferredWidth: 1
        Layout.minimumWidth: 0
        implicitHeight: tabContent.implicitHeight + Tokens.padding.small * 2
        radius: Tokens.rounding.large
        color: active ? Colours.palette.m3primaryContainer : Colours.tPalette.m3surfaceContainer

        Behavior on color {
            CAnim {}
        }

        StateLayer {
            radius: tab.radius
            color: tab.foreground
            onClicked: AiUsage.tab = tab.tabId
        }

        // Keyboard hint for Alt+N.
        StyledText {
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: Tokens.padding.extraSmall
            visible: tab.shortcut <= 9
            text: tab.shortcut
            font: Tokens.font.label.small
            color: Qt.alpha(tab.foreground, 0.5)
        }

        ColumnLayout {
            id: tabContent

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: Tokens.padding.small
            spacing: Tokens.spacing.extraSmall

            ProviderLogo {
                Layout.alignment: Qt.AlignHCenter
                visible: tab.provider.length > 0
                provider: tab.provider
                colour: tab.active ? tab.foreground : tab.colour
            }

            MaterialIcon {
                Layout.alignment: Qt.AlignHCenter
                visible: tab.icon.length > 0
                text: tab.icon
                color: tab.active ? tab.foreground : tab.colour
                fontStyle: Tokens.font.icon.medium
            }

            StyledText {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                text: tab.text
                font: Tokens.font.label.builders.medium.weight(tab.active ? Font.DemiBold : Font.Medium).build()
                color: tab.foreground
                elide: Text.ElideRight
            }

            StyledRect {
                Layout.fillWidth: true
                Layout.preferredHeight: Tokens.sizes.aiUsage.modelBarHeight
                opacity: tab.meter >= 0 ? 1 : 0
                radius: Tokens.rounding.full
                color: Qt.alpha(tab.colour, 0.2)

                StyledRect {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: parent.width * Math.max(0, tab.meter)
                    radius: Tokens.rounding.full
                    color: tab.meter < 0.1 ? Colours.palette.m3error : tab.colour
                }
            }
        }
    }
}
