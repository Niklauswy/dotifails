pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Wysun.Config
import qs.components
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

        delegate: OverlayWindow {
            id: win

            readonly property real pad: 48

            surface: "launcher"
            active: open && Config.launcher.enabled
            // Opens with an expressive spring (it overshoots slightly), closes with a quick fade.
            openAnim: Anim.DefaultSpatial
            closeAnim: Anim.FastEffects
            // LauncherPanel.handleKey: Escape leaves a menu, the preview or a folder before closing.
            closeOnEscape: false
            anchors.top: true
            margins.top: Math.max(8, modelData.height * 0.12 - pad)
            implicitWidth: panel.panelWidth + pad * 2
            implicitHeight: panel.panelHeight + pad * 2
            mask: Region {
                item: panel.surface
            }

            onActiveChanged: {
                if (active)
                    Qt.callLater(() => panel.focusSearch());
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
