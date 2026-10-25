pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.containers
import qs.components.controls
import qs.components.filedialog
import qs.services
import qs.utils

// Coverflow wallpaper picker. Original Wysun code; the card strip follows the
// visual reference supplied for the task (tall cards, tilted and overlapped
// towards a larger, front-facing selection).
Scope {
    id: root

    Variants {
        model: Quickshell.screens

        delegate: StyledWindow {
            id: win

            required property ShellScreen modelData
            readonly property ScreenState state: ShellState.forScreen(modelData)
            property real reveal: state.wallpapers ? 1 : 0

            Behavior on reveal {
                Anim {}
            }

            Tokens.screen: modelData.name
            name: "wallpapers"
            screen: modelData
            visible: state.wallpapers || reveal > 0.001
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: state.wallpapers ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
            anchors {
                top: true
                bottom: true
                left: true
                right: true
            }
            color: "transparent"

            property bool libraryOpen

            function sync(): void {
                if (state.wallpapers) {
                    filter.text = "";
                    if (!libraryOpen)
                        WallpaperLibrary.open();
                    libraryOpen = true;
                    carousel.reset();
                    Qt.callLater(() => filter.forceActiveFocus());
                } else if (libraryOpen) {
                    libraryOpen = false;
                    WallpaperLibrary.close();
                }
            }

            Component.onDestruction: {
                if (libraryOpen)
                    WallpaperLibrary.close();
            }

            // The state survives shell reloads, so a picker left open comes back populated.
            Component.onCompleted: {
                if (state.wallpapers)
                    sync();
            }

            Connections {
                target: win.state

                function onWallpapersChanged(): void {
                    win.sync();
                }
            }

            Connections {
                target: WallpaperLibrary

                function onEntriesChanged(): void {
                    if (win.state.wallpapers)
                        carousel.reset();
                }
            }

            // Scriptable control of the open picker (`wysun-shell` IPC: wallpapers go|select|filter|apply|state).
            IpcHandler {
                enabled: win.state.wallpapers
                target: "wallpapers"

                function go(delta: int): void {
                    carousel.go(delta);
                }

                function select(position: int): void {
                    carousel.move(position);
                }

                function filter(text: string): void {
                    filter.text = text;
                }

                function apply(): void {
                    carousel.apply();
                }

                function random(): void {
                    carousel.random();
                }

                function state(): string {
                    return JSON.stringify({ settled: carousel.settled, query: filter.text, index: carousel.index, count: carousel.items.length, cards: cards.count, selected: carousel.items[carousel.index]?.path ?? "" });
                }
            }

            HyprlandFocusGrab {
                active: win.state.wallpapers
                windows: [win]
                onCleared: win.state.wallpapers = false
            }

            Rectangle {
                anchors.fill: parent
                color: Colours.palette.m3scrim
                opacity: 0.5 * Math.max(0, Math.min(1, win.reveal))

                MouseArea {
                    anchors.fill: parent
                    onClicked: win.state.wallpapers = false
                    onWheel: wheel => carousel.wheelStep(wheel.angleDelta.y)
                }
            }

            Item {
                id: carousel

                readonly property int radius: 8
                readonly property real cardHeight: Math.min(win.height * 0.62, 760)
                readonly property real cardWidth: cardHeight * 0.6
                readonly property string query: filter.text.trim().toLowerCase()
                readonly property var items: {
                    const all = WallpaperLibrary.entries;
                    return query ? all.filter(e => e.name.toLowerCase().includes(query) || (query === "animated" && e.animated)) : all;
                }
                readonly property string currentPath: Wallpapers.forOutput(win.modelData.name)
                property int index: 0
                property real pos: 0
                property bool settled
                property real wheelAcc

                function reset(): void {
                    const found = items.findIndex(e => e.path === currentPath);
                    index = Math.max(found, 0);
                    snap.restart();
                    pos = index;
                    syncWindow();
                    settled = false;
                    settle.restart();
                }

                function go(delta: int): void {
                    move(index + delta);
                }

                function move(target: int): void {
                    const next = Math.max(0, Math.min(items.length - 1, target));
                    if (next === index)
                        return;
                    index = next;
                    settled = false;
                    settle.restart();
                    pos = next;
                }

                function wheelStep(delta: real): void {
                    wheelAcc += delta;
                    while (Math.abs(wheelAcc) >= 120) {
                        go(wheelAcc > 0 ? -1 : 1);
                        wheelAcc -= wheelAcc > 0 ? 120 : -120;
                    }
                }

                function apply(): void {
                    const entry = items[index];
                    if (!entry)
                        return;
                    Wallpapers.setWallpaper(entry.path);
                    closeTimer.restart();
                }

                // Apply a wallpaper other than the current one, picked at random from what the filter shows.
                function random(): void {
                    const pool = items.filter(e => e.path !== currentPath);
                    if (pool.length === 0)
                        return;
                    Wallpapers.setWallpaper(pool[Math.floor(Math.random() * pool.length)].path);
                    closeTimer.restart();
                }

                // The picker covers the screen, so it steps aside while the file dialog is open.
                function add(): void {
                    addDialog.open();
                    win.state.wallpapers = false;
                }

                // Keep only the cards near the selection alive (virtualised strip).
                function syncWindow(): void {
                    const base = Math.round(pos);
                    const lo = Math.max(0, base - radius), hi = Math.min(items.length - 1, base + radius);
                    const have = {};
                    for (let i = cards.count - 1; i >= 0; i--) {
                        const idx = cards.get(i).idx;
                        if (idx < lo || idx > hi)
                            cards.remove(i);
                        else
                            have[idx] = true;
                    }
                    const missing = [];
                    for (let i = lo; i <= hi; i++)
                        if (!have[i])
                            missing.push(i);
                    missing.sort((x, y) => Math.abs(x - pos) - Math.abs(y - pos));
                    for (const i of missing)
                        cards.append({ idx: i });
                }

                anchors.fill: parent
                opacity: Math.max(0, Math.min(1, win.reveal))
                scale: 0.94 + 0.06 * opacity
                onPosChanged: syncWindow()
                onItemsChanged: {
                    cards.clear();
                    const found = query ? -1 : items.findIndex(e => e.path === currentPath);
                    index = found >= 0 ? found : query ? 0 : Math.min(index, Math.max(items.length - 1, 0));
                    pos = index;
                    syncWindow();
                    settled = false;
                    settle.restart();
                }

                // Spring towards the selected index; `snap` jumps without animating.
                Behavior on pos {
                    enabled: !snap.running

                    SpringAnimation {
                        spring: 4.2
                        damping: 0.4
                        epsilon: 0.0005
                    }
                }

                Timer {
                    id: snap

                    interval: 50
                }

                Timer {
                    id: settle

                    interval: 450
                    onTriggered: carousel.settled = true
                }

                Timer {
                    id: closeTimer

                    interval: 260
                    onTriggered: win.state.wallpapers = false
                }

                FileDialog {
                    id: addDialog

                    title: Tr.tr("Select a wallpaper")
                    filterLabel: Tr.tr("Images and videos")
                    filters: Images.validImageExtensions.concat(["bmp", "gif", "mp4", "webm", "mkv"])
                    onAccepted: path => Wallpapers.setWallpaper(path)
                }

                ListModel {
                    id: cards
                }

                Item {
                    id: strip

                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.verticalCenterOffset: -Tokens.padding.extraExtraLarge
                    width: parent.width
                    height: carousel.cardHeight

                    Repeater {
                        model: cards

                        delegate: WallpaperCard {
                            id: item

                            required property int idx

                            entry: carousel.items[idx] ?? ({ path: "", animated: false })
                            t: idx - carousel.pos
                            cardWidth: carousel.cardWidth
                            cardHeight: carousel.cardHeight
                            centerX: strip.width / 2
                            selected: idx === carousel.index
                            current: entry.path === carousel.currentPath
                            settled: carousel.settled
                            onClicked: idx === carousel.index ? carousel.apply() : carousel.move(idx)
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        z: -1000
                        acceptedButtons: Qt.NoButton
                        onWheel: wheel => carousel.wheelStep(wheel.angleDelta.y)
                    }
                }

                Column {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: strip.bottom
                    anchors.topMargin: Tokens.spacing.extraLarge
                    spacing: Tokens.spacing.small

                    StyledText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: carousel.items[carousel.index]?.name ?? (WallpaperLibrary.scanning ? "Loading wallpapers…" : "No wallpapers found")
                        color: Colours.palette.m3onSurface
                        font: Tokens.font.title.small
                    }

                    StyledText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: carousel.items.length > 0
                        text: `${carousel.index + 1} / ${carousel.items.length}  ·  ← → browse  ·  Enter apply  ·  Ctrl+R random  ·  Esc close`
                        color: Colours.palette.m3onSurfaceVariant
                        font: Tokens.font.label.small
                    }

                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: Tokens.spacing.small

                        IconButton {
                            anchors.verticalCenter: parent.verticalCenter
                            icon: "add_photo_alternate"
                            type: IconButton.Tonal
                            isRound: true
                            onClicked: carousel.add()
                        }

                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            implicitWidth: Tokens.sizes.launcher.itemWidth * 0.6
                            implicitHeight: filter.implicitHeight + Tokens.padding.small * 2
                            radius: Tokens.rounding.full
                            color: Colours.tPalette.m3surfaceContainer
                            border.width: 1
                            border.color: filter.activeFocus ? Colours.palette.m3primary : Colours.palette.m3outlineVariant

                            MaterialIcon {
                                id: searchIcon

                                anchors.left: parent.left
                                anchors.leftMargin: Tokens.padding.medium
                                anchors.verticalCenter: parent.verticalCenter
                                text: "search"
                                color: Colours.palette.m3onSurfaceVariant
                                fontStyle: Tokens.font.icon.small
                            }

                            TextInput {
                                id: filter

                                anchors.left: searchIcon.right
                                anchors.right: parent.right
                                anchors.margins: Tokens.padding.medium
                                anchors.verticalCenter: parent.verticalCenter
                                color: Colours.palette.m3onSurface
                                selectionColor: Colours.palette.m3primary
                                selectedTextColor: Colours.palette.m3onPrimary
                                font: Tokens.font.body.small
                                clip: true
                                focus: true

                                StyledText {
                                    anchors.fill: parent
                                    visible: !filter.text
                                    text: "Filter wallpapers"
                                    color: Colours.palette.m3outline
                                    font: filter.font
                                }

                                Keys.priority: Keys.BeforeItem
                                Keys.onPressed: event => {
                                    const key = event.key;
                                    if ((event.modifiers & Qt.ControlModifier) && key === Qt.Key_R)
                                        carousel.random();
                                    else if (key === Qt.Key_Left || key === Qt.Key_Up)
                                        carousel.go(-1);
                                    else if (key === Qt.Key_Right || key === Qt.Key_Down)
                                        carousel.go(1);
                                    else if (key === Qt.Key_PageUp)
                                        carousel.go(-5);
                                    else if (key === Qt.Key_PageDown)
                                        carousel.go(5);
                                    else if (key === Qt.Key_Home)
                                        carousel.move(0);
                                    else if (key === Qt.Key_End)
                                        carousel.move(carousel.items.length - 1);
                                    else if (key === Qt.Key_Return || key === Qt.Key_Enter)
                                        carousel.apply();
                                    else if (key === Qt.Key_Escape)
                                        win.state.wallpapers = false;
                                    else
                                        return;
                                    event.accepted = true;
                                }
                            }
                        }

                        IconButton {
                            anchors.verticalCenter: parent.verticalCenter
                            icon: "shuffle"
                            type: IconButton.Tonal
                            isRound: true
                            onClicked: carousel.random()
                        }
                    }
                }
            }
        }
    }
}
