pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Wysun.Config
import qs.components
import qs.components.containers
import qs.components.controls
import qs.services
import qs.modules.launcher.services

// Emoji drawer: same surface, radii, nav rail and motion as the launcher.
Scope {
    id: root

    readonly property var categories: [
        {id: "Recent", icon: "history"},
        {id: "All", icon: "emoji_emotions"},
        {id: "Smileys", icon: "mood"},
        {id: "People", icon: "waving_hand"},
        {id: "Nature", icon: "eco"},
        {id: "Food", icon: "restaurant"},
        {id: "Travel", icon: "flight"},
        {id: "Objects & symbols", icon: "category"}
    ]
    property var recents: []
    readonly property string recentsPath: `${Quickshell.env("HOME")}/.local/state/wysun/emoji-recent.json`

    function remember(row: var): void {
        const entry = {kind: "emoji", value: row.value, title: row.title, keywords: row.keywords ?? "", category: row.category ?? ""};
        recents = [entry].concat(recents.filter(r => r.value !== row.value)).slice(0, 32);
        store.setText(JSON.stringify(recents));
    }

    FileView {
        id: store
        path: root.recentsPath
        onLoaded: { try { root.recents = JSON.parse(text()); } catch (error) { root.recents = []; } }
        onLoadFailed: root.recents = []
    }

    Variants {
        model: Quickshell.screens
        delegate: StyledWindow {
            id: win
            required property ShellScreen modelData
            readonly property ScreenState state: ShellState.forScreen(modelData)
            property string category: "All"
            property string copied
            readonly property string needle: search.text.trim().toLowerCase()
            readonly property var filtered: {
                if (!needle && category === "Recent")
                    return root.recents;
                return source.rows.filter(r => (category === "All" || category === "Recent" || r.category === category) && (!needle || (r.keywords + " " + r.value).toLowerCase().includes(needle)));
            }
            property real reveal: state.emoji ? 1 : 0
            Behavior on reveal { Anim {} }

            Tokens.screen: modelData.name
            name: "emoji"
            screen: modelData
            visible: state.emoji || reveal > 0.001
            anchors.bottom: true
            margins.bottom: Config.border.thickness
            implicitWidth: Math.min(screen.width - Tokens.padding.extraExtraLarge * 2, Tokens.sizes.launcher.itemWidth * 1.6)
            implicitHeight: Math.min(screen.height - Tokens.padding.extraExtraLarge * 2, Tokens.sizes.launcher.itemHeight * 10 + Tokens.padding.extraLarge * 3)
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: state.emoji ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

            function choose(id: string): void {
                category = id;
                search.forceActiveFocus();
            }
            function cycle(step: int): void {
                const index = root.categories.findIndex(c => c.id === category);
                choose(root.categories[(index + step + root.categories.length) % root.categories.length].id);
            }
            function pick(row: var, paste: bool): void {
                if (!row) return;
                root.remember(row);
                if (paste) {
                    LauncherData.paste(row);
                    state.emoji = false;
                } else {
                    LauncherData.copy(row);
                    copied = row.value;
                    closeTimer.restart();
                }
            }
            onVisibleChanged: {
                if (visible) {
                    copied = "";
                    category = root.recents.length ? "Recent" : "All";
                    search.clear();
                    source.refresh();
                    Qt.callLater(() => search.forceActiveFocus());
                }
            }

            Timer { id: closeTimer; interval: 420; onTriggered: win.state.emoji = false }
            HyprlandFocusGrab {
                active: win.state.emoji
                windows: [win]
                onCleared: win.state.emoji = false
            }
            DataSource { id: source; mode: "emoji"; enabled: win.visible }

            Rectangle {
                id: surface
                width: parent.width
                height: parent.height
                radius: Tokens.rounding.large
                color: Colours.tPalette.m3surface
                opacity: Math.max(0, Math.min(1, win.reveal))
                y: (1 - win.reveal) * (height + Config.border.thickness)

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Tokens.padding.large
                    spacing: Tokens.spacing.large

                    RowLayout {
                        spacing: Tokens.spacing.medium
                        MaterialIcon { text: "emoji_emotions"; color: Colours.palette.m3primary; fontStyle: Tokens.font.icon.large }
                        StyledText { text: "Emoji"; font: Tokens.font.title.medium }
                        StyledText { text: "Pick one to copy it"; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.body.small; Layout.fillWidth: true }
                        StyledText { text: "Super + Ctrl + ."; color: Colours.palette.m3outline; font: Tokens.font.label.small }
                        IconButton { icon: "close"; type: IconButton.Text; onClicked: win.state.emoji = false }
                    }

                    SearchBar {
                        id: search
                        objectName: "emojiSearch"
                        Layout.fillWidth: true
                        font: Tokens.font.body.large
                        placeholderText: "Search emoji by name or feeling…"
                        onAccepted: win.pick(grid.currentItem?.modelData, false)
                        Keys.onEscapePressed: win.state.emoji = false
                        Keys.onUpPressed: grid.moveCurrentIndexUp()
                        Keys.onDownPressed: grid.moveCurrentIndexDown()
                        Keys.onLeftPressed: event => { if (!text) { grid.moveCurrentIndexLeft(); event.accepted = true; } else event.accepted = false; }
                        Keys.onRightPressed: event => { if (!text) { grid.moveCurrentIndexRight(); event.accepted = true; } else event.accepted = false; }
                        Keys.onPressed: event => {
                            if ((event.modifiers & Qt.AltModifier) && event.key >= Qt.Key_1 && event.key <= Qt.Key_8) {
                                win.choose(root.categories[event.key - Qt.Key_1].id); event.accepted = true;
                            } else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
                                win.cycle((event.modifiers & Qt.ShiftModifier) || event.key === Qt.Key_Backtab ? -1 : 1); event.accepted = true;
                            } else if ((event.modifiers & Qt.ControlModifier) && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
                                win.pick(grid.currentItem?.modelData, true); event.accepted = true;
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: Tokens.spacing.large

                        ColumnLayout {
                            Layout.preferredWidth: Tokens.sizes.launcher.itemWidth / 4
                            Layout.maximumWidth: Tokens.sizes.launcher.itemWidth / 4
                            Layout.alignment: Qt.AlignTop
                            spacing: Tokens.spacing.extraSmall
                            Repeater {
                                model: root.categories
                                delegate: Rectangle {
                                    id: nav
                                    required property var modelData
                                    readonly property bool active: win.category === modelData.id
                                    Layout.fillWidth: true
                                    implicitHeight: Tokens.sizes.launcher.itemHeight * 0.72
                                    radius: Tokens.rounding.medium
                                    color: active ? Colours.palette.m3secondaryContainer : "transparent"
                                    StateLayer { radius: nav.radius; onClicked: win.choose(nav.modelData.id) }
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Tokens.padding.small
                                        spacing: Tokens.spacing.small
                                        MaterialIcon { text: nav.modelData.icon; fontStyle: Tokens.font.icon.small; color: nav.active ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant }
                                        StyledText { text: nav.modelData.id; font: Tokens.font.label.medium; color: nav.active ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface; elide: Text.ElideRight; Layout.fillWidth: true }
                                    }
                                }
                            }
                            Item { Layout.fillHeight: true }
                            StyledText { text: "Tab to browse\nAlt + 1–8 to jump"; font: Tokens.font.label.small; color: Colours.palette.m3outline; lineHeight: 1.5 }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: Tokens.spacing.small
                            RowLayout {
                                Layout.fillWidth: true
                                StyledText { text: win.needle ? "Results" : win.category === "Recent" ? "Recently used" : win.category; font: Tokens.font.title.small; Layout.fillWidth: true }
                                StyledText { text: source.loading ? "Searching…" : grid.count + " emoji"; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
                            }
                            GridView {
                                id: grid
                                objectName: "emojiGrid"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true
                                cellWidth: width / 9
                                cellHeight: cellWidth
                                currentIndex: 0
                                model: ScriptModel { values: win.filtered; onValuesChanged: grid.currentIndex = 0 }
                                highlightMoveDuration: Tokens.anim.durations.expressiveFastEffects
                                delegate: Rectangle {
                                    id: emoji
                                    required property var modelData
                                    required property int index
                                    width: grid.cellWidth - Tokens.spacing.extraSmall
                                    height: grid.cellHeight - Tokens.spacing.extraSmall
                                    radius: Tokens.rounding.medium
                                    color: GridView.isCurrentItem ? Colours.palette.m3secondaryContainer : "transparent"
                                    StyledText { anchors.centerIn: parent; text: emoji.modelData.value; font: Tokens.font.headline.medium }
                                    StateLayer {
                                        radius: emoji.radius
                                        onContainsMouseChanged: { if (containsMouse) grid.currentIndex = emoji.index; }
                                        onClicked: win.pick(emoji.modelData, false)
                                    }
                                }
                                StyledText {
                                    anchors.centerIn: parent
                                    visible: !grid.count
                                    text: source.loading ? "Loading emoji…" : win.category === "Recent" && !win.needle ? "Emoji you copy will show up here" : "No emoji found. Try another word."
                                    color: Colours.palette.m3onSurfaceVariant
                                    font: Tokens.font.body.medium
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Tokens.spacing.small
                        MaterialIcon {
                            visible: !!win.copied
                            text: "check_circle"
                            color: Colours.palette.m3primary
                            fontStyle: Tokens.font.icon.small
                        }
                        StyledText {
                            text: win.copied ? `Copied ${win.copied}` : (grid.currentItem?.modelData.title ?? "Pick an emoji")
                            color: win.copied ? Colours.palette.m3primary : Colours.palette.m3onSurface
                            font: Tokens.font.body.small
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        StyledText { text: "↵ Copy   Ctrl + ↵ Paste   Esc Close"; color: Colours.palette.m3outline; font: Tokens.font.label.small }
                    }
                }
            }
        }
    }
}
