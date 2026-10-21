// Adapted from end-4/dots-hyprland overview/OverviewWindow.qml and drag handling
// in OverviewWidget.qml (GPL-3.0), modified for Wysun.
// Source: 2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8; see THIRD_PARTY.md.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland
import Wysun.Config
import qs.components
import qs.services
import "OverviewGeometry.js" as Geometry

Rectangle {
    id: root
    required property string outputName
    required property var client
    required property real workspaceWidth
    required property real workspaceHeight
    required property Item dragCanvas
    signal focusRequested()
    readonly property var ipc: client.lastIpcObject
    readonly property var monitor: client.monitor?.lastIpcObject ?? {}
    readonly property var bounds: Geometry.geometry(ipc, monitor, workspaceWidth, workspaceHeight)
    readonly property real homeX: bounds.x
    readonly property real homeY: bounds.y
    x: homeX
    y: homeY
    width: bounds.width
    height: bounds.height
    radius: Tokens.rounding.small
    color: Colours.palette.m3surfaceContainerHigh
    border.width: mouse.containsMouse ? 2 : 1
    border.color: mouse.containsMouse ? Colours.palette.m3primary : Colours.palette.m3outlineVariant
    z: ipc.fullscreen ? 3 : ipc.floating ? 2 : 1
    Drag.active: mouse.drag.active
    Drag.source: root
    Drag.keys: ["wysun-window"]
    Drag.hotSpot.x: width / 2
    Drag.hotSpot.y: height / 2
    opacity: mouse.drag.active ? 0.8 : 1
    ScreencopyView {
        anchors.centerIn: parent
        captureSource: root.client.wayland
        live: true
        constraintSize.width: root.width - root.border.width * 2
        constraintSize.height: root.height - root.border.width * 2
    }
    Rectangle {
        anchors.centerIn: parent
        width: Math.min(root.width, Tokens.font.icon.large.pixelSize + Tokens.padding.medium * 2)
        height: width
        radius: Tokens.rounding.medium
        color: Colours.palette.m3surfaceContainer
        Image {
            id: appIcon
            readonly property var entry: DesktopEntries.heuristicLookup(root.ipc.class)
            anchors.fill: parent
            anchors.margins: Tokens.padding.small
            source: entry?.icon ? Quickshell.iconPath(entry.icon, true) : ""
            fillMode: Image.PreserveAspectFit
        }
        MaterialIcon {
            anchors.centerIn: parent
            visible: appIcon.status !== Image.Ready
            text: "window"
            color: Colours.palette.m3onSurface
            fontStyle: Tokens.font.icon.large
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        drag.target: root
        drag.filterChildren: true
        property Item originalParent
        onPressed: event => {
            originalParent = root.parent;
        }
        onPositionChanged: {
            if (drag.active && root.parent !== root.dragCanvas) {
                const point = root.mapToItem(root.dragCanvas, 0, 0);
                root.parent = root.dragCanvas;
                root.x = point.x; root.y = point.y;
                root.z = 100;
            }
        }
        onReleased: {
            if (drag.active) root.Drag.drop();
            restore();
        }
        onCanceled: restore()
        function restore() {
            if (originalParent) root.parent = originalParent;
            root.x = Qt.binding(() => root.homeX);
            root.y = Qt.binding(() => root.homeY);
            root.z = Qt.binding(() => root.ipc.fullscreen ? 3 : root.ipc.floating ? 2 : 1);
        }
        onClicked: event => {
            const address = root.ipc.address;
            if (event.button === Qt.MiddleButton)
                Hypr.dispatch(Hypr.usingLua ? `hl.dsp.window.close({window="address:${address}"})` : `closewindow address:${address}`);
            else {
                root.focusRequested();
                Hypr.dispatch(Hypr.usingLua ? `hl.dsp.focus({window="address:${address}"})` : `focuswindow address:${address}`);
            }
        }
    }
    ToolTip {
        Tokens.screen: root.outputName
        visible: mouse.containsMouse && !mouse.pressed
        text: root.client.title
        delay: 700
        padding: Tokens.padding.medium
        contentItem: StyledText {
            text: root.client.title
            font: Tokens.font.body.medium
            color: Colours.palette.m3onSurface
            elide: Text.ElideRight
        }
        background: Rectangle {
            radius: Tokens.rounding.small
            color: Colours.palette.m3surfaceContainerHighest
            border.color: Colours.palette.m3outlineVariant
            border.width: 1
        }
    }
}
