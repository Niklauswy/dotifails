// Adapted from end-4/dots-hyprland overview/OverviewWidget.qml (GPL-3.0).
// Source: 2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8; see THIRD_PARTY.md.
// A compact card with a rows x columns grid of workspaces, centred at the top.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects
import Quickshell
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import "OverviewGeometry.js" as Geometry

Item {
    id: root
    required property ShellScreen screen
    required property var screenState
    property bool open: true
    signal closed()

    readonly property var monitor: Hypr.monitorFor(screen)
    readonly property var monitorData: monitor?.lastIpcObject ?? {}
    readonly property var area: Geometry.usable(monitorData)

    // end-4 defaults: 2 rows x 5 columns, each workspace about 0.18 of the screen.
    // The card is capped so it never spans the whole width of the output.
    readonly property int rows: 2
    readonly property int columns: 5
    readonly property real scaleRatio: 0.18
    readonly property real maxCardRatio: 0.74
    readonly property real workspaceSpacing: 5
    readonly property real cardPadding: 10
    readonly property real workspaceWidth: Math.round(Math.min(screen.width * scaleRatio,
        (screen.width * maxCardRatio - cardPadding * 2 - workspaceSpacing * (columns - 1)) / columns))
    readonly property real workspaceHeight: Math.round(workspaceWidth * area.height / area.width)
    readonly property real largeRadius: Tokens.rounding.large
    readonly property real smallRadius: Tokens.rounding.small
    readonly property real shadowMargin: 24

    readonly property int activeWorkspaceId: Math.max(1, Math.min(100, monitor?.activeWorkspace?.id ?? 1))
    readonly property int perGroup: rows * columns
    property int group: Math.floor((activeWorkspaceId - 1) / perGroup)

    property int draggingFrom: -1
    property int draggingTarget: -1

    // Enter and exit: opacity, scale and slide with end-4's emphasized curves.
    property real reveal: 0
    Behavior on reveal {
        NumberAnimation {
            duration: root.open ? Tokens.anim.durations.normal : Tokens.anim.durations.small
            easing: root.open ? Tokens.anim.emphasizedDecel : Tokens.anim.emphasizedAccel
        }
    }
    onRevealChanged: if (reveal === 0 && !open) closed()

    focus: true
    Component.onCompleted: {
        searchBar.forceActiveFocus();
        reveal = Qt.binding(() => root.open ? 1 : 0);
    }
    Keys.onEscapePressed: close()

    function cell(workspace) { return Geometry.cell(workspace, rows, columns); }
    function close() {
        for (const output of Quickshell.screens) {
            const state = ShellState.forScreen(output);
            if (state) { state.overview = false; state.overviewKeyboard = false; }
        }
    }
    function search(text) {
        const panels = ShellState.componentsFor(screen)?.panels;
        if (!panels?.launcher?.available) return;
        close();
        screenState.launcherQuery = text;
        screenState.launcher = true;
    }
    function cornerRadius(row, column, vertical, horizontal) {
        const atTop = row === 0, atBottom = row === rows - 1;
        const atLeft = column === 0, atRight = column === columns - 1;
        return ((vertical === "top" ? atTop : atBottom) && (horizontal === "left" ? atLeft : atRight)) ? largeRadius : smallRadius;
    }

    MouseArea { anchors.fill: parent; onClicked: root.close() }

    Item {
        id: card
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: Tokens.spacing.extraLarge + (1 - root.reveal) * -Tokens.spacing.extraLarge * 2
        width: column.implicitWidth
        height: column.implicitHeight
        opacity: root.reveal
        scale: 0.92 + 0.08 * root.reveal
        transformOrigin: Item.Top

        Column {
            id: column
            spacing: Tokens.spacing.medium

            SearchBar {
                id: searchBar
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(background.width, root.workspaceWidth * 2.4)
                placeholderText: "Search, calculate or run"
                bg.border.width: 1
                bg.border.color: Colours.palette.m3outlineVariant
                onTextEdited: { if (text.length) root.search(text); }
                onPressed: root.search(text)
                onAccepted: root.search(text)
                Keys.onEscapePressed: root.close()
            }

            Item {
                width: background.width + root.shadowMargin * 2
                height: background.height + root.shadowMargin * 2
                anchors.horizontalCenter: parent.horizontalCenter

                RectangularShadow {
                    anchors.fill: background
                    radius: background.radius
                    color: Qt.alpha(Colours.palette.m3shadow, 0.5)
                    blur: root.shadowMargin * 0.9
                    spread: 1
                    offset: Qt.vector2d(0, 1)
                    cached: true
                }

                Rectangle {
                    id: background
                    anchors.centerIn: parent
                    width: workspaces.width + root.cardPadding * 2
                    height: workspaces.height + root.cardPadding * 2
                    radius: root.largeRadius + root.cardPadding
                    color: Colours.palette.m3surfaceContainer
                    border.width: 1
                    border.color: Qt.alpha(Colours.palette.m3outlineVariant, 0.5)

                    MouseArea { anchors.fill: parent }

                    Item {
                        id: workspaces
                        anchors.centerIn: parent
                        width: root.columns * root.workspaceWidth + (root.columns - 1) * root.workspaceSpacing
                        height: root.rows * root.workspaceHeight + (root.rows - 1) * root.workspaceSpacing

                        Repeater {
                            model: root.perGroup
                            Rectangle {
                                id: workspace
                                required property int index
                                readonly property int workspaceId: root.group * root.perGroup + index + 1
                                readonly property var position: root.cell(workspaceId)
                                property bool hoveredWhileDragging: false
                                x: position.column * (root.workspaceWidth + root.workspaceSpacing)
                                y: position.row * (root.workspaceHeight + root.workspaceSpacing)
                                width: root.workspaceWidth
                                height: root.workspaceHeight
                                topLeftRadius: root.cornerRadius(position.row, position.column, "top", "left")
                                topRightRadius: root.cornerRadius(position.row, position.column, "top", "right")
                                bottomLeftRadius: root.cornerRadius(position.row, position.column, "bottom", "left")
                                bottomRightRadius: root.cornerRadius(position.row, position.column, "bottom", "right")
                                color: hoveredWhileDragging
                                    ? Qt.tint(Colours.palette.m3surfaceContainerLow, Qt.alpha(Colours.palette.m3onSurface, 0.1))
                                    : workspaceArea.containsMouse
                                        ? Qt.tint(Colours.palette.m3surfaceContainerLow, Qt.alpha(Colours.palette.m3onSurface, 0.05))
                                        : Colours.palette.m3surfaceContainerLow
                                border.width: 2
                                border.color: hoveredWhileDragging ? Qt.alpha(Colours.palette.m3onSurface, 0.12) : "transparent"
                                Behavior on color { ColorAnimation { duration: Tokens.anim.durations.expressiveFastEffects; easing: Tokens.anim.expressiveFastEffects } }

                                StyledText {
                                    anchors.centerIn: parent
                                    text: workspace.workspaceId
                                    color: Qt.alpha(Colours.palette.m3onSurfaceVariant, 0.2)
                                    font.pixelSize: root.workspaceHeight * 0.55
                                    font.weight: Font.DemiBold
                                }
                                MouseArea {
                                    id: workspaceArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: {
                                        if (root.draggingTarget !== -1) return;
                                        root.close();
                                        Hypr.focusWorkspace(workspace.workspaceId);
                                    }
                                }
                                DropArea {
                                    anchors.fill: parent
                                    keys: ["wysun-window"]
                                    onEntered: {
                                        root.draggingTarget = workspace.workspaceId;
                                        if (root.draggingFrom !== workspace.workspaceId) workspace.hoveredWhileDragging = true;
                                    }
                                    onExited: {
                                        workspace.hoveredWhileDragging = false;
                                        if (root.draggingTarget === workspace.workspaceId) root.draggingTarget = -1;
                                    }
                                }
                            }
                        }

                        Item {
                            id: windowSpace
                            anchors.fill: parent

                            Repeater {
                                model: ScriptModel {
                                    values: Hypr.toplevels.values.filter(t => {
                                        const id = t.workspace?.id ?? -1;
                                        return id > root.group * root.perGroup && id <= (root.group + 1) * root.perGroup
                                            && !Hypr.isToplevelIgnored(t);
                                    })
                                }
                                OverviewWindow {
                                    required property var modelData
                                    client: modelData
                                    outputName: root.screen.name
                                    widgetMonitorId: root.monitor?.id ?? -1
                                    workspaceWidth: root.workspaceWidth
                                    workspaceHeight: root.workspaceHeight
                                    workspaceSpacing: root.workspaceSpacing
                                    rows: root.rows
                                    columns: root.columns
                                    group: root.group
                                    largeRadius: root.largeRadius
                                    smallRadius: root.smallRadius
                                    onFocusRequested: root.close()
                                    onDragStarted: from => root.draggingFrom = from
                                    onDragFinished: root.draggingFrom = -1
                                    draggingTarget: root.draggingTarget
                                }
                            }

                            Rectangle {
                                id: indicator
                                readonly property var position: root.cell(root.activeWorkspaceId)
                                visible: Math.floor((root.activeWorkspaceId - 1) / root.perGroup) === root.group
                                x: position.column * (root.workspaceWidth + root.workspaceSpacing)
                                y: position.row * (root.workspaceHeight + root.workspaceSpacing)
                                z: 1000
                                width: root.workspaceWidth
                                height: root.workspaceHeight
                                color: "transparent"
                                border.width: 2
                                border.color: Colours.palette.m3secondary
                                topLeftRadius: root.cornerRadius(position.row, position.column, "top", "left")
                                topRightRadius: root.cornerRadius(position.row, position.column, "top", "right")
                                bottomLeftRadius: root.cornerRadius(position.row, position.column, "bottom", "left")
                                bottomRightRadius: root.cornerRadius(position.row, position.column, "bottom", "right")
                                Behavior on x { Anim { type: Anim.FastEffects } }
                                Behavior on y { Anim { type: Anim.FastEffects } }
                                Behavior on topLeftRadius { Anim { type: Anim.FastEffects } }
                                Behavior on topRightRadius { Anim { type: Anim.FastEffects } }
                                Behavior on bottomLeftRadius { Anim { type: Anim.FastEffects } }
                                Behavior on bottomRightRadius { Anim { type: Anim.FastEffects } }
                            }
                        }
                    }
                }
            }
        }
    }
}
