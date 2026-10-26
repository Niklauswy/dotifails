pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.launcher.services

// Emoji drawer: search, one row of recents and a roomy grid; same surface, radii and motion as the launcher.
Scope {
    id: root

    readonly property int columns: 9
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

    // One emoji cell: the selection fades in behind it and the glyph grows a little.
    component EmojiCell: Item {
        id: cell
        required property string value
        property bool current
        property bool copied
        signal chosen()
        signal hovered()

        Rectangle {
            anchors.fill: parent
            anchors.margins: Tokens.spacing.extraSmall
            radius: Tokens.rounding.large
            color: Colours.palette.m3secondaryContainer
            opacity: cell.current ? 1 : area.containsMouse ? 0.45 : 0
            Behavior on opacity { Anim { type: Anim.FastEffects } }
        }
        StyledText {
            anchors.centerIn: parent
            text: cell.value
            font: Tokens.font.headline.large
            scale: cell.copied ? 1.45 : cell.current ? 1.2 : area.containsMouse ? 1.08 : 1
            Behavior on scale { Anim { type: Anim.FastSpatial } }
        }
        MouseArea {
            id: area
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onPositionChanged: cell.hovered()
            onClicked: cell.chosen()
        }
    }

    Variants {
        model: Quickshell.screens
        delegate: OverlayWindow {
            id: win
            property string copied
            property string zone: "grid"
            property int recentIndex: 0
            readonly property string needle: search.text.trim().toLowerCase()
            readonly property var filtered: needle ? source.rows.filter(r => (r.keywords + " " + r.value).toLowerCase().includes(needle)) : source.rows
            readonly property var recentRows: root.recents.slice(0, root.columns)
            readonly property bool showRecents: !needle && recentRows.length > 0
            readonly property var selected: showRecents && zone === "recent" ? recentRows[recentIndex] : filtered[grid.currentIndex]

            surface: "emoji"
            anchors.bottom: true
            // Window-level sizes read the content item's tokens: that Item inherits the screen, while
            // the window's own binding may not be set yet when these are first evaluated.
            margins.bottom: contentItem.Tokens.padding.large
            implicitWidth: Math.min(screen.width - contentItem.Tokens.padding.extraExtraLarge * 2, Tokens.sizes.launcher.itemWidth * 1.15)
            implicitHeight: Math.min(screen.height - contentItem.Tokens.padding.extraExtraLarge * 2, Tokens.sizes.launcher.itemHeight * 10 + contentItem.Tokens.padding.extraLarge * 3)

            function pick(row: var, paste: bool): void {
                if (!row) return;
                root.remember(row);
                if (paste) {
                    LauncherData.paste(row);
                    close();
                } else {
                    LauncherData.copy(row);
                    copied = row.value;
                    closeTimer.restart();
                }
            }
            function step(dx: int, dy: int): void {
                if (showRecents && zone === "recent") {
                    if (dy > 0) { zone = "grid"; grid.currentIndex = Math.min(recentIndex, Math.max(0, filtered.length - 1)); }
                    else recentIndex = Math.max(0, Math.min(recentRows.length - 1, recentIndex + dx));
                } else if (dy < 0 && showRecents && grid.currentIndex < root.columns) {
                    zone = "recent";
                    recentIndex = Math.min(grid.currentIndex, recentRows.length - 1);
                } else if (dy) {
                    dy < 0 ? grid.moveCurrentIndexUp() : grid.moveCurrentIndexDown();
                } else {
                    dx < 0 ? grid.moveCurrentIndexLeft() : grid.moveCurrentIndexRight();
                }
            }
            onVisibleChanged: {
                if (visible) {
                    copied = "";
                    zone = "grid";
                    recentIndex = 0;
                    search.clear();
                    grid.currentIndex = 0;
                    source.refresh();
                    Qt.callLater(() => search.forceActiveFocus());
                }
            }

            Timer { id: closeTimer; interval: 480; onTriggered: win.close() }
            DataSource { id: source; mode: "emoji"; enabled: win.visible }

            Rectangle {
                id: card
                width: parent.width
                height: parent.height
                radius: Tokens.rounding.large
                color: Colours.tPalette.m3surface
                opacity: Math.max(0, Math.min(1, win.reveal))
                y: (1 - win.reveal) * (height + Tokens.padding.large)

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Tokens.padding.large
                    spacing: Tokens.spacing.medium

                    SearchBar {
                        id: search
                        objectName: "emojiSearch"
                        Layout.fillWidth: true
                        font: Tokens.font.body.large
                        placeholderText: "Search emoji"
                        onAccepted: win.pick(win.selected, false)
                        onTextChanged: win.zone = "grid"
                        Keys.onUpPressed: win.step(0, -1)
                        Keys.onDownPressed: win.step(0, 1)
                        Keys.onLeftPressed: event => { if (!text) { win.step(-1, 0); event.accepted = true; } else event.accepted = false; }
                        Keys.onRightPressed: event => { if (!text) { win.step(1, 0); event.accepted = true; } else event.accepted = false; }
                        Keys.onPressed: event => {
                            if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
                                const back = (event.modifiers & Qt.ShiftModifier) || event.key === Qt.Key_Backtab;
                                win.zone = "grid";
                                back ? grid.moveCurrentIndexLeft() : grid.moveCurrentIndexRight();
                                event.accepted = true;
                            } else if ((event.modifiers & Qt.ControlModifier) && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
                                win.pick(win.selected, true); event.accepted = true;
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: win.showRecents
                        spacing: Tokens.spacing.extraSmall
                        StyledText { text: "Recent"; font: Tokens.font.label.medium; color: Colours.palette.m3onSurfaceVariant; Layout.leftMargin: Tokens.padding.small }
                        Row {
                            Layout.fillWidth: true
                            Repeater {
                                model: win.recentRows
                                delegate: EmojiCell {
                                    required property var modelData
                                    required property int index
                                    width: grid.cellWidth
                                    height: grid.cellHeight
                                    value: modelData.value
                                    current: win.zone === "recent" && win.recentIndex === index
                                    copied: current && win.copied === value
                                    onHovered: { win.zone = "recent"; win.recentIndex = index; }
                                    onChosen: win.pick(modelData, false)
                                }
                            }
                        }
                    }

                    GridView {
                        id: grid
                        objectName: "emojiGrid"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        cellWidth: Math.floor(width / root.columns)
                        cellHeight: cellWidth
                        currentIndex: 0
                        boundsBehavior: Flickable.StopAtBounds
                        model: ScriptModel { values: win.filtered; onValuesChanged: grid.currentIndex = 0 }
                        delegate: EmojiCell {
                            required property var modelData
                            required property int index
                            width: grid.cellWidth
                            height: grid.cellHeight
                            value: modelData.value
                            current: win.zone === "grid" && grid.currentIndex === index
                            copied: current && win.copied === value
                            onHovered: { win.zone = "grid"; grid.currentIndex = index; }
                            onChosen: win.pick(modelData, false)
                        }
                        StyledText {
                            anchors.centerIn: parent
                            visible: !grid.count
                            text: source.loading ? "Loading emoji…" : "No emoji found"
                            color: Colours.palette.m3onSurfaceVariant
                            font: Tokens.font.body.medium
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: Tokens.padding.small
                        spacing: Tokens.spacing.small
                        MaterialIcon {
                            opacity: win.copied ? 1 : 0
                            text: "check_circle"
                            color: Colours.palette.m3primary
                            fontStyle: Tokens.font.icon.small
                            Behavior on opacity { Anim { type: Anim.FastEffects } }
                        }
                        StyledText {
                            text: win.copied ? "Copied" : (win.selected?.title ?? "")
                            color: win.copied ? Colours.palette.m3primary : Colours.palette.m3onSurfaceVariant
                            font: Tokens.font.body.small
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }
    }
}
