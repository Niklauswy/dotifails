// Adapted from end-4/dots-hyprland cheatsheet (GPL-3.0): keycap rendering and category columns.
// Source: dots/.config/quickshell/ii/modules/ii/cheatsheet; see THIRD_PARTY.md.
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

// Key cheat sheet generated from the active Hyprland binds (backend.py).
Scope {
    id: root

    property var groups: []
    readonly property string script: Quickshell.shellPath("modules/cheatsheet/backend.py")

    Process {
        id: loader
        command: ["python3", "-I", root.script, `${Quickshell.env("HOME")}/.config/wysun/hyprland.lua`]
        stdout: StdioCollector {
            onStreamFinished: { try { root.groups = JSON.parse(text); } catch (error) { root.groups = []; } }
        }
    }

    Variants {
        model: Quickshell.screens
        delegate: StyledWindow {
            id: win
            required property ShellScreen modelData
            readonly property ScreenState state: ShellState.forScreen(modelData)
            property real reveal: state.cheatsheet ? 1 : 0
            Behavior on reveal { Anim {} }

            Tokens.screen: modelData.name
            name: "cheatsheet"
            screen: modelData
            visible: state.cheatsheet || reveal > 0.001
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: state.cheatsheet ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
            anchors { top: true; bottom: true; left: true; right: true }
            color: "transparent"

            onVisibleChanged: {
                if (visible && state.cheatsheet) { loader.running = false; loader.running = true; Qt.callLater(() => keys.forceActiveFocus()); }
            }
            HyprlandFocusGrab {
                active: win.state.cheatsheet
                windows: [win]
                onCleared: win.state.cheatsheet = false
            }

            Rectangle {
                anchors.fill: parent
                color: Colours.palette.m3scrim
                opacity: 0.45 * Math.max(0, Math.min(1, win.reveal))
                MouseArea { anchors.fill: parent; onClicked: win.state.cheatsheet = false }
            }

            Item {
                id: keys
                anchors.fill: parent
                focus: true
                Keys.onEscapePressed: win.state.cheatsheet = false
            }

            Rectangle {
                id: surface
                anchors.centerIn: parent
                anchors.verticalCenterOffset: (1 - win.reveal) * Tokens.padding.extraExtraLarge
                width: Math.min(win.width - Tokens.padding.extraExtraLarge * 2, Tokens.sizes.launcher.itemWidth * 2.6)
                height: Math.min(win.height - Tokens.padding.extraExtraLarge * 2, content.implicitHeight + Tokens.padding.extraLarge * 2)
                radius: Tokens.rounding.large
                color: Colours.tPalette.m3surface
                opacity: Math.max(0, Math.min(1, win.reveal))
                MouseArea { anchors.fill: parent }

                ColumnLayout {
                    id: content
                    anchors.fill: parent
                    anchors.margins: Tokens.padding.extraLarge
                    spacing: Tokens.spacing.large

                    RowLayout {
                        spacing: Tokens.spacing.medium
                        MaterialIcon { text: "keyboard"; color: Colours.palette.m3primary; fontStyle: Tokens.font.icon.large }
                        StyledText { text: "Keyboard shortcuts"; font: Tokens.font.title.medium }
                        StyledText { text: "From your active Hyprland config"; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.body.small; Layout.fillWidth: true }
                        StyledText { text: "Super + /"; color: Colours.palette.m3outline; font: Tokens.font.label.small }
                        IconButton { icon: "close"; type: IconButton.Text; onClicked: win.state.cheatsheet = false }
                    }

                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredHeight: columns.implicitHeight
                        contentHeight: columns.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        Flow {
                            id: columns
                            width: parent.width
                            spacing: Tokens.spacing.extraLarge
                            Repeater {
                                model: root.groups
                                delegate: ColumnLayout {
                                    id: group
                                    required property var modelData
                                    width: (columns.width - columns.spacing * 2) / 3
                                    spacing: Tokens.spacing.small
                                    StyledText { text: group.modelData.category; font: Tokens.font.title.small; color: Colours.palette.m3primary }
                                    Repeater {
                                        model: group.modelData.items
                                        delegate: RowLayout {
                                            id: row
                                            required property var modelData
                                            Layout.fillWidth: true
                                            spacing: Tokens.spacing.small
                                            Row {
                                                spacing: Tokens.spacing.extraSmall
                                                Repeater {
                                                    model: row.modelData.keys
                                                    delegate: Rectangle {
                                                        id: cap
                                                        required property string modelData
                                                        implicitWidth: Math.max(implicitHeight, label.implicitWidth + Tokens.padding.small * 2)
                                                        implicitHeight: label.implicitHeight + Tokens.padding.small
                                                        radius: Tokens.rounding.small
                                                        color: Colours.palette.m3surfaceContainerHigh
                                                        border.width: 1
                                                        border.color: Colours.palette.m3outlineVariant
                                                        StyledText { id: label; anchors.centerIn: parent; text: cap.modelData; font: Tokens.font.label.small; color: Colours.palette.m3onSurface }
                                                    }
                                                }
                                            }
                                            StyledText { text: row.modelData.label; font: Tokens.font.body.small; color: Colours.palette.m3onSurfaceVariant; elide: Text.ElideRight; Layout.fillWidth: true }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
