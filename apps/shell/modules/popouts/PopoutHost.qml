// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/drawers/ContentWindow.qml (sin BlobGroup ni MultiEffect), modules/drawers/Interactions.qml
// y modules/drawers/Panels.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import "../../" as Wysun
import "../../utils/PopoutGeometry.js" as Geometry
import "../quicksettings" as QuickSettingsModule

// One host per enabled output. Exactly one of them can be the target of the
// shared ShellState, so only that host requests exclusive keyboard focus.
PanelWindow {
    id: host
    required property var controller
    required property var motion
    required property var modelData
    screen: modelData

    readonly property var state: controller.state
    readonly property string surface: controller.surface
    readonly property bool targetVisible: controller.opened && controller.screenName === modelData.name
    readonly property bool active: popup.retained
    property var focusReturn: null

    readonly property real targetWidth: Math.min(panel.owned ? panel.targetWidth : card.preferredWidth, Math.max(320, width - Wysun.Appearance.spaceXl * 4))
    readonly property real targetHeight: Math.min(panel.owned ? panel.targetHeight : card.preferredHeight, Math.max(280, height - Wysun.Appearance.spaceXl * 4))
    readonly property var targetRect: Geometry.centeredRect(width, height, targetWidth, targetHeight)

    visible: popup.retained
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    // While the card is only finishing its closing morph the output must not
    // swallow clicks meant for the windows below.
    mask: targetVisible ? null : passThrough
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "wysun-popout"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: targetVisible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

    // Capture the invocation control before ShellState.close() clears it, and
    // restore it only after the closing morph has ended and the overlay is
    // unmapped. The immediate restore in ShellState remains a fallback.
    onTargetVisibleChanged: {
        if (targetVisible) {
            focusReturn = state.returnFocusItem;
            Qt.callLater(function() {
                if (host.targetVisible) wrapper.forceActiveFocus();
            });
        }
    }

    Connections {
        target: popup
        function onPhaseChanged() {
            // A host that is not the current target must not overwrite the
            // phase of another output during an interrupted transition.
            if (host.state.screenName === host.modelData.name)
                host.state.phase = popup.phase;
            if (popup.phase === "closed" && host.focusReturn) {
                var item = host.focusReturn;
                host.focusReturn = null;
                Qt.callLater(function() {
                    if (item && item.visible && item.enabled)
                        item.forceActiveFocus();
                });
            }
        }
    }

    PopoutState {
        id: popup
        motion: host.motion
        requested: host.targetVisible
    }

    Regions { id: regions }

    Shortcut {
        sequence: "Escape"
        context: Qt.WindowShortcut
        enabled: host.targetVisible
        onActivated: host.controller.close()
    }

    HyprlandFocusGrab {
        id: grab
        active: host.targetVisible
        windows: [host]
        onCleared: if (host.targetVisible) host.controller.close()
    }

    Region { id: passThrough }

    Interactions {
        anchors.fill: parent
        z: 0
        controller: host.controller
        active: host.targetVisible
    }

    Wrapper {
        id: wrapper
        z: 1
        motion: host.motion
        progress: popup.progress
        originRect: regions.anchorRect(host.state.anchorX, host.state.anchorY, 72, 64, host.width, host.height)
        targetRect: host.targetRect
        contentOpacity: host.motion && host.motion.reducedMotion ? 1 : Math.max(0, Math.min(1, (progress - 0.15) / 0.6))
        focus: host.targetVisible
        onEscapePressed: host.controller.close()

        PopoutCard {
            id: card
            anchors.fill: parent
            controller: host.controller
            motion: host.motion
            monitorName: host.modelData.name
            visible: !panel.owned
            framed: false
            live: true
            sampling: host.visible
        }
        QuickSettingsModule.SurfacePanel {
            id: panel
            anchors.fill: parent
            controller: host.controller
            motion: host.motion
            hostActive: host.active
        }
    }
}
