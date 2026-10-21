pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Wysun.Config
import qs.components
import qs.components.containers
import qs.services

// Raycast-style launcher: one floating panel in the upper third of the focused screen.
Scope {
    id: root

    readonly property alias variants: variants

    Variants {
        id: variants

        model: Quickshell.screens

        delegate: StyledWindow {
            id: win

            required property ShellScreen modelData
            readonly property ScreenState state: ShellState.forScreen(modelData)
            readonly property bool active: state.launcher && Config.launcher.enabled
            property real reveal: active ? 1 : 0
            readonly property real pad: 40

            Behavior on reveal {
                NumberAnimation {
                    duration: Tokens.anim.durations.small * 0.9
                                        easing: Tokens.anim.standard
                }
            }

            Tokens.screen: modelData.name
            name: "launcher"
            screen: modelData
            visible: active || reveal > 0.001
            anchors.top: true
            margins.top: Math.max(8, modelData.height * 0.13 - pad)
            implicitWidth: panel.panelWidth + pad * 2
            implicitHeight: panel.maxPanelHeight + pad * 2
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: active ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
            mask: Region {
                item: panel.surface
            }

            onActiveChanged: {
                if (active)
                    Qt.callLater(() => panel.focusSearch());
            }

            HyprlandFocusGrab {
                active: win.active
                windows: [win]
                onCleared: win.state.launcher = false
            }

            readonly property alias panelItem: panel

            LauncherPanel {
                id: panel

                x: win.pad
                y: win.pad
                screen: win.modelData
                state: win.state
                reveal: win.reveal
            }
        }
    }
}
