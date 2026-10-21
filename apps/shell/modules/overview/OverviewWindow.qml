// Adapted from end-4/dots-hyprland overview/OverviewWindow.qml and the drag handling
// in OverviewWidget.qml (GPL-3.0), modified for Wysun.
// Source: 2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8; see THIRD_PARTY.md.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import Quickshell
import Quickshell.Wayland
import Wysun.Config
import qs.components
import qs.services
import "OverviewGeometry.js" as Geometry

Item {
    id: root
    required property var client
    required property string outputName
    required property int widgetMonitorId
    required property real workspaceWidth
    required property real workspaceHeight
    required property real workspaceSpacing
    required property int rows
    required property int columns
    required property int group
    required property real largeRadius
    required property real smallRadius
    property int draggingTarget: -1
    signal focusRequested()
    signal dragStarted(int from)
    signal dragFinished()

    readonly property var ipc: client.lastIpcObject
    readonly property var monitor: client.monitor?.lastIpcObject ?? {}
    readonly property int actualWorkspace: client.workspace?.id ?? 1
    // After a drop the window heads for its new tile before Hyprland reports it.
    property int droppedWorkspace: -1
    readonly property int workspaceId: droppedWorkspace > 0 ? droppedWorkspace : actualWorkspace
    onActualWorkspaceChanged: droppedWorkspace = -1

    readonly property var slot: Geometry.cell(workspaceId, rows, columns)
    readonly property real tileX: slot.column * (workspaceWidth + workspaceSpacing)
    readonly property real tileY: slot.row * (workspaceHeight + workspaceSpacing)
    readonly property var bounds: Geometry.geometry(ipc, monitor, workspaceWidth, workspaceHeight)
    readonly property real homeX: Math.round(tileX + bounds.x)
    readonly property real homeY: Math.round(tileY + bounds.y)
    readonly property bool dragging: mouse.drag.active
    property bool hovered: mouse.containsMouse
    property bool pressed: mouse.pressed

    x: homeX
    y: homeY
    width: bounds.width
    height: bounds.height
    opacity: (client.monitor?.id ?? widgetMonitorId) === widgetMonitorId ? 1 : 0.4
    z: dragging ? 99999 : 1 + (ipc.floating ? 1 : 0) + (ipc.fullscreen ? 2 : 0)
    Drag.active: dragging
    Drag.source: root
    Drag.keys: ["wysun-window"]

    // Corners that touch the edge of the grid follow the card, the rest stay tight.
    readonly property real minRadius: Tokens.rounding.small
    readonly property bool atTop: slot.row === 0
    readonly property bool atBottom: slot.row === rows - 1
    readonly property bool atLeft: slot.column === 0
    readonly property bool atRight: slot.column === columns - 1
    readonly property real fromLeft: bounds.x
    readonly property real fromTop: bounds.y
    readonly property real fromRight: workspaceWidth - (bounds.x + bounds.width)
    readonly property real fromBottom: workspaceHeight - (bounds.y + bounds.height)
    readonly property real topLeftRadius: Math.max((atTop && atLeft ? largeRadius : smallRadius) - Math.max(fromLeft, fromTop), minRadius)
    readonly property real topRightRadius: Math.max((atTop && atRight ? largeRadius : smallRadius) - Math.max(fromRight, fromTop), minRadius)
    readonly property real bottomLeftRadius: Math.max((atBottom && atLeft ? largeRadius : smallRadius) - Math.max(fromLeft, fromBottom), minRadius)
    readonly property real bottomRightRadius: Math.max((atBottom && atRight ? largeRadius : smallRadius) - Math.max(fromRight, fromBottom), minRadius)

    readonly property bool compact: Tokens.font.body.small.pixelSize * 4 > Math.min(width, height)
    readonly property real iconSize: Math.min(width, height) * (compact ? 0.6 : 0.35)

    Behavior on x { enabled: !root.dragging; animation: moveAnim }
    Behavior on y { enabled: !root.dragging; animation: moveAnim }
    Behavior on width { animation: moveAnim }
    Behavior on height { animation: moveAnim }
    NumberAnimation {
        id: moveAnim
        alwaysRunToEnd: true
        duration: Tokens.anim.durations.normal
        easing: Tokens.anim.emphasizedDecel
    }

    Item {
        id: content
        anchors.fill: parent
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: mask
            maskSpreadAtMin: 1
            maskThresholdMin: 0.5
        }

        ScreencopyView {
            anchors.fill: parent
            captureSource: root.client.wayland
            live: true

            Rectangle {
                anchors.fill: parent
                color: root.pressed ? Qt.alpha(Colours.palette.m3onSurface, 0.2)
                    : root.hovered ? Qt.alpha(Colours.palette.m3onSurface, 0.1)
                    : "transparent"
                border.width: 1
                border.color: Qt.alpha(Colours.palette.m3outline, 0.12)
                Behavior on color { ColorAnimation { duration: Tokens.anim.durations.expressiveFastEffects; easing: Tokens.anim.expressiveFastEffects } }
            }

            Image {
                id: appIcon
                readonly property var entry: DesktopEntries.heuristicLookup(root.ipc.class)
                anchors.centerIn: parent
                width: root.iconSize
                height: root.iconSize
                sourceSize: Qt.size(width * 2, height * 2)
                source: entry?.icon ? Quickshell.iconPath(entry.icon, true) : ""
                fillMode: Image.PreserveAspectFit
                mipmap: true
                visible: status === Image.Ready
                Behavior on width { animation: moveAnim }
                Behavior on height { animation: moveAnim }
            }
            MaterialIcon {
                anchors.centerIn: parent
                visible: appIcon.status !== Image.Ready
                text: "window"
                color: Colours.palette.m3onSurface
                fontStyle: Tokens.font.icon.large
            }
        }
    }

    Rectangle {
        id: mask
        width: root.width
        height: root.height
        topLeftRadius: root.topLeftRadius
        topRightRadius: root.topRightRadius
        bottomLeftRadius: root.bottomLeftRadius
        bottomRightRadius: root.bottomRightRadius
        layer.enabled: true
        visible: false
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        drag.target: root
        onPressed: event => {
            if (event.button !== Qt.LeftButton) return;
            root.Drag.hotSpot.x = event.x;
            root.Drag.hotSpot.y = event.y;
            root.dragStarted(root.workspaceId);
        }
        onReleased: event => {
            const target = root.draggingTarget;
            const wasDragging = root.dragging;
            if (wasDragging) root.Drag.drop();
            root.dragFinished();
            // Dropping releases the drag binding; restore it so the window glides home.
            if (wasDragging) {
                if (target !== -1 && target !== root.actualWorkspace) {
                    root.droppedWorkspace = target;
                    Hypr.dispatch(Hypr.usingLua
                        ? `hl.dsp.window.move({workspace=${target},follow=false,window="address:${root.ipc.address}"})`
                        : `movetoworkspacesilent ${target},address:${root.ipc.address}`);
                }
                root.x = Qt.binding(() => root.homeX);
                root.y = Qt.binding(() => root.homeY);
            }
        }
        onCanceled: {
            root.dragFinished();
            root.x = Qt.binding(() => root.homeX);
            root.y = Qt.binding(() => root.homeY);
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
        visible: mouse.containsMouse && !root.dragging && !mouse.pressed
        delay: 700
        padding: Tokens.padding.medium
        contentItem: StyledText {
            text: `${root.client.title}\n[${root.ipc.class}]${root.ipc.xwayland ? " [XWayland]" : ""}`
            font: Tokens.font.body.medium
            color: Colours.palette.m3onSurface
        }
        background: Rectangle {
            radius: Tokens.rounding.small
            color: Colours.palette.m3surfaceContainerHighest
            border.color: Colours.palette.m3outlineVariant
            border.width: 1
        }
    }
}
