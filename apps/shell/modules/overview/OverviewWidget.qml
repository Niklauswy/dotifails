// Adapted from end-4/dots-hyprland overview/OverviewWidget.qml (GPL-3.0).
// Source: 2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8; see THIRD_PARTY.md.
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services

Rectangle {
    id: root
    required property ShellScreen screen
    required property var screenState
    readonly property var monitor: Hypr.monitorFor(screen)
    property int group: Math.floor((Math.max(1, monitor?.activeWorkspace?.id ?? 1) - 1) / 10)
    readonly property real gap: Tokens.spacing.large
    readonly property real tileWidth: (grid.width - gap * 4) / 5
    readonly property real tileHeight: Math.min(tileWidth * screen.height / screen.width, (height * 0.62 - gap) / 2)
    color: Colours.palette.m3surface
    function close() { screenState.overview = false; }
    function search(text) {
        const panels = ShellState.componentsFor(screen)?.panels;
        if (!panels?.launcher?.available) return;
        close();
        screenState.launcherQuery = text;
        screenState.launcher = true;
    }
    focus: true
    Component.onCompleted: searchBar.forceActiveFocus()
    Keys.onEscapePressed: close()

    MouseArea { anchors.fill: parent; onClicked: root.close() }
    Column {
        anchors.centerIn: parent
        width: parent.width - Tokens.padding.extraLarge * 4
        spacing: Tokens.spacing.extraLarge
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Tokens.spacing.large
            StyledText { text: "Workspaces"; font: Tokens.font.headline.medium }
            StyledText { text: root.screen.name; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.body.medium; anchors.verticalCenter: parent.verticalCenter }
        }
        SearchBar {
            id: searchBar
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(parent.width, root.tileWidth * 3)
            placeholderText: "Search, calculate or run"
            onTextEdited: { if (text.length) root.search(text); }
            onPressed: root.search(text)
            onAccepted: root.search(text)
            Keys.onEscapePressed: root.close()
        }
        Grid {
            id: grid
            width: parent.width
            columns: 5
            rows: 2
            spacing: root.gap
            Repeater {
                model: 10
                Rectangle {
                    id: tile
                    required property int index
                    readonly property int workspaceId: root.group * 10 + index + 1
                    readonly property var workspace: Hypr.workspaces.values.find(w => w.id === workspaceId)
                    readonly property var clients: Hypr.toplevels.values.filter(t => t.workspace?.id === workspaceId && !Hypr.isToplevelIgnored(t))
                    readonly property bool current: root.monitor?.activeWorkspace?.id === workspaceId
                    width: root.tileWidth
                    height: root.tileHeight
                    radius: Tokens.rounding.large
                    color: drop.containsDrag ? Colours.palette.m3secondaryContainer : Colours.palette.m3surfaceContainerLow
                    border.width: current || drop.containsDrag ? 2 : 1
                    border.color: current || drop.containsDrag ? Colours.palette.m3primary : Colours.palette.m3outlineVariant
                    StyledText {
                        anchors.centerIn: parent
                        text: tile.workspaceId
                        visible: tile.clients.length === 0
                        font: Tokens.font.headline.large
                        color: Colours.palette.m3onSurfaceVariant
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { Hypr.focusWorkspace(tile.workspaceId); root.close(); }
                    }
                    Item {
                        id: canvas
                        anchors.fill: parent
                        anchors.margins: Tokens.padding.small
                        Repeater {
                            model: ScriptModel { values: tile.clients }
                            OverviewWindow {
                                required property var modelData
                                client: modelData
                                workspaceWidth: canvas.width
                                workspaceHeight: canvas.height
                                dragCanvas: grid
                                onFocusRequested: root.close()
                            }
                        }
                    }
                    DropArea {
                        id: drop
                        anchors.fill: parent
                        keys: ["wysun-window"]
                        onDropped: event => {
                            const client = event.source?.client;
                            if (!client || client.workspace?.id === tile.workspaceId) return;
                            const address = client.lastIpcObject.address;
                            Hypr.dispatch(Hypr.usingLua
                                ? `hl.dsp.window.move({workspace=${tile.workspaceId},follow=false,window="address:${address}"})`
                                : `movetoworkspacesilent ${tile.workspaceId},address:${address}`);
                            event.acceptProposedAction();
                        }
                    }
                    StyledText {
                        anchors.left: parent.left
                        anchors.top: parent.bottom
                        anchors.topMargin: Tokens.spacing.small
                        text: tile.workspaceId + (tile.workspace?.monitor?.name ? "  ·  " + tile.workspace.monitor.name : "")
                        font: Tokens.font.body.small
                        color: tile.current ? Colours.palette.m3primary : Colours.palette.m3onSurfaceVariant
                    }
                }
            }
            rowSpacing: root.gap + Tokens.font.body.small.pixelSize + Tokens.spacing.small
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Tokens.spacing.large
            IconButton { icon: "chevron_left"; enabled: root.group > 0; onClicked: root.group-- }
            StyledText { text: "Drag to move  ·  Click to focus  ·  Middle-click to close  ·  Esc to leave"; font: Tokens.font.body.medium; color: Colours.palette.m3onSurfaceVariant; anchors.verticalCenter: parent.verticalCenter }
            IconButton { icon: "chevron_right"; onClicked: root.group++ }
        }
    }
}
