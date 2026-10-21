pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Wysun.Config
import qs.components
import qs.components.containers
import qs.components.controls
import qs.services
import qs.modules.launcher.services

Scope {
    id: root
    Variants {
        model: Quickshell.screens
        delegate: StyledWindow {
            id: win
            required property ShellScreen modelData
            readonly property ScreenState state: ShellState.forScreen(modelData)
            property string category: "All"
            readonly property var filtered: source.rows.filter(r => (category === "All" || r.category === category) && (!search.text || (r.keywords + " " + r.value).toLowerCase().includes(search.text.toLowerCase())))
            property real reveal: state.emoji ? 1 : 0
            Behavior on reveal { Anim { type: Anim.DefaultEffects } }
            Tokens.screen: modelData.name
            name: "emoji"
            screen: modelData
            visible: reveal > 0
            anchors.top: true
            anchors.left: false
            anchors.right: false
            margins.top: Tokens.padding.extraLarge
            implicitWidth: Math.min(screen.width - Tokens.padding.extraExtraLarge * 2, Tokens.sizes.launcher.itemWidth)
            implicitHeight: Math.min(screen.height - Tokens.padding.extraExtraLarge * 2, Tokens.sizes.launcher.itemHeight * 8)
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: state.emoji ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
            function pick(row: var, paste: bool): void {
                if (!row) return;
                if (paste) LauncherData.paste(row); else LauncherData.copy(row);
                state.emoji = false;
            }
            onVisibleChanged: {
                if (visible) { category = "All"; search.clear(); source.refresh(); Qt.callLater(() => search.forceActiveFocus()); }
            }
            HyprlandFocusGrab {
                active: win.state.emoji
                windows: [win]
                onCleared: win.state.emoji = false
            }
            DataSource { id: source; mode: "emoji"; enabled: win.visible }
            Rectangle {
                id: surface
                anchors.fill: parent
                radius: Tokens.rounding.extraLarge
                color: Colours.tPalette.m3surface
                border.width: 1
                border.color: Colours.palette.m3outlineVariant
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Tokens.padding.large
                    spacing: Tokens.spacing.medium
                    RowLayout {
                        MaterialIcon { text: "emoji_emotions"; color: Colours.palette.m3primary; fontStyle: Tokens.font.icon.large }
                        StyledText { text: "Emoji"; font: Tokens.font.title.large; Layout.fillWidth: true }
                        StyledText { text: "Wysun"; font: Tokens.font.label.medium; color: Colours.palette.m3onSurfaceVariant }
                        IconButton { icon: "close"; type: IconButton.Text; onClicked: win.state.emoji = false }
                    }
                    SearchBar {
                        id: search
                        objectName: "emojiSearch"
                        Layout.fillWidth: true
                        placeholderText: "Find a feeling, a thing, a little spark…"
                        onAccepted: win.pick(grid.currentItem?.modelData, false)
                        Keys.onEscapePressed: win.state.emoji = false
                        Keys.onLeftPressed: event => { if (!text) { grid.moveCurrentIndexLeft(); event.accepted = true; } else event.accepted = false; }
                        Keys.onRightPressed: event => { if (!text) { grid.moveCurrentIndexRight(); event.accepted = true; } else event.accepted = false; }
                        Keys.onUpPressed: grid.moveCurrentIndexUp()
                        Keys.onDownPressed: grid.moveCurrentIndexDown()
                        Keys.onPressed: event => {
                            if ((event.modifiers & Qt.ControlModifier) && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) { win.pick(grid.currentItem?.modelData, true); event.accepted = true; }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Tokens.spacing.extraSmall
                        Repeater {
                            model: ["All", "Smileys", "People", "Nature", "Food", "Travel", "Objects & symbols"]
                            delegate: TextButton {
                                required property string modelData
                                text: modelData
                                type: TextButton.Text
                                font: Tokens.font.label.small
                                horizontalPadding: Tokens.padding.small
                                checked: win.category === modelData
                                onClicked: { win.category = modelData; search.forceActiveFocus(); }
                            }
                        }
                    }
                    GridView {
                        id: grid
                        objectName: "emojiGrid"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        cellWidth: width / 8
                        cellHeight: Tokens.sizes.launcher.itemHeight
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
                            ToolTip.visible: emojiMouse.hovered
                            ToolTip.text: modelData.title
                            HoverHandler { id: emojiMouse }
                        }
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }
                    StyledText {
                        visible: !grid.count
                        text: source.loading ? "Loading emoji…" : "No emoji found. Try another word."
                        color: Colours.palette.m3onSurfaceVariant
                        font: Tokens.font.body.medium
                        Layout.alignment: Qt.AlignHCenter
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        StyledText { text: grid.currentItem?.modelData.title || "Pick a little expression"; font: Tokens.font.body.small; elide: Text.ElideRight; Layout.fillWidth: true }
                        StyledText { text: "↵ Copy   Ctrl + ↵ Paste   Esc Close"; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.label.small }
                    }
                }
                opacity: win.reveal
                transform: Translate { y: -surface.Tokens.spacing.extraLarge * (1 - win.reveal) }
            }
        }
    }
}
