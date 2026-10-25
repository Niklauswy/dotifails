pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Wysun.Config
import qs.components
import qs.components.containers
import qs.services
import qs.modules.launcher.services

// Raycast-style launcher in Material 3 Expressive: one floating panel in the upper
// third of the focused screen that springs open and settles.
Scope {
    id: root

    readonly property alias variants: variants

    EditMorph {}

    // `wysun-shell ipc call launcher activate`: what Enter does on the selected row (scripted checks of a hand-over).
    IpcHandler {
        target: "launcher"

        function activate(): bool {
            for (const win of root.variants.instances)
                if (win.active) {
                    win.panelItem.activate(win.panelItem.row);
                    return true;
                }
            return false;
        }
    }

    Variants {
        id: variants

        model: Quickshell.screens

        delegate: StyledWindow {
            id: win

            required property ShellScreen modelData
            readonly property ScreenState state: ShellState.forScreen(modelData)
            readonly property bool active: state.launcher && Config.launcher.enabled
            // 0 → 1 on open with an expressive spring (it overshoots slightly), a quick fade on close.
            property real reveal: active ? 1 : 0
            readonly property real pad: 48

            Behavior on reveal {
                Anim {
                    type: win.active ? Anim.DefaultSpatial : Anim.FastEffects
                }
            }

            Tokens.screen: modelData.name
            name: "launcher"
            screen: modelData
            visible: active || reveal > 0.001
            anchors.top: true
            margins.top: Math.max(8, modelData.height * 0.12 - pad)
            implicitWidth: panel.panelWidth + pad * 2
            implicitHeight: panel.panelHeight + pad * 2
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
                originX: (win.modelData.width - win.width) / 2
                originY: win.margins.top
                screen: win.modelData
                state: win.state
                reveal: win.reveal
            }
        }
    }
}
