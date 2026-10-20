// Adaptado de caelestia-dots/shell/modules/drawers/ContentWindow.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import "../../" as Wysun
import "../../components" as Components
import "../../utils/PopoutGeometry.js" as Geometry

PanelWindow {
    id: host
    required property var controller
    required property var motion
    required property var modelData
    screen: modelData
    readonly property bool targetVisible: controller.opened && controller.screenName === modelData.name
    property bool active: false
    property real progress: 0

    visible: active || targetVisible
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "wysun-popout"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: targetVisible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

    onTargetVisibleChanged: {
        if (targetVisible) {
            active = true;
            grab.active = true;
        } else {
            grab.active = false;
        }
        progress = targetVisible ? 1 : 0;
    }
    onProgressChanged: {
        if (targetVisible && progress >= 1) controller.state.phase = "open";
        else if (!targetVisible && progress <= 0) {
            active = false;
            controller.state.phase = "closed";
        }
    }

    Behavior on progress {
        Components.Anim { motion: host.motion; type: Components.Anim.Emphasized }
    }

    Shortcut {
        sequence: "Escape"
        context: Qt.WindowShortcut
        enabled: host.targetVisible
        onActivated: host.controller.close()
    }

    HyprlandFocusGrab {
        id: grab
        windows: [host]
        onCleared: if (host.targetVisible) host.controller.close()
    }

    MouseArea {
        anchors.fill: parent
        z: 0
        acceptedButtons: Qt.AllButtons
        onClicked: host.controller.close()
    }

    PopoutCard {
        id: card
        z: 1
        motion: host.motion
        controller: host.controller
        monitorName: host.modelData.name
        contentOpacity: Math.max(0, Math.min(1, (host.progress - 0.35) / 0.65))

        readonly property real targetWidth: Math.min(620, Math.max(320, host.width - Wysun.Appearance.spaceXl * 2))
        readonly property real targetHeight: Math.min(420, Math.max(300, host.height - Wysun.Appearance.spaceXl * 2))
        readonly property var geometry: Geometry.popoutGeometry(host.width, host.height,
            host.controller.state.anchorX, host.controller.state.anchorY, targetWidth, targetHeight,
            host.motion.reducedMotion ? 1 : host.progress)
        width: geometry.width
        height: geometry.height
        x: geometry.x
        y: geometry.y
        opacity: host.progress
    }
}
