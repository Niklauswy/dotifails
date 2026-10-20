// Adaptado de caelestia-dots/shell/modules/osd/Wrapper.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// One host per output. It appears for every PipeWire volume/mute/microphone
// change (including the existing multimedia keys) and for sysfs brightness
// changes, then hides on its own. It never takes keyboard focus or input.
import QtQuick
import Quickshell
import Quickshell.Wayland
import "../../" as Wysun
import "../../components" as Components
import "../../services" as Services

PanelWindow {
    id: root

    required property var motion
    required property var modelData

    screen: modelData
    property bool active: false
    property string mode: "volume"
    property real progress: active ? 1 : 0
    readonly property int hideDelay: Math.max(1200, Wysun.Appearance.motionEnter * 8)

    visible: active || progress > 0.001
    anchors { top: true; bottom: true; right: true }
    implicitWidth: Wysun.Appearance.spaceXl * 16
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    exclusiveZone: 0
    WlrLayershell.namespace: "wysun-osd"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    mask: Region {}

    Services.Audio { id: audio }
    Services.Brightness { id: brightness }

    function showMode(channel) {
        if (channel === "brightness" && !brightness.available) return;
        if (channel !== "brightness" && !audio.available) return;
        if (channel === "source-volume" || channel === "source-mute") {
            if (!audio.sourceAvailable) return;
            mode = channel;
        } else {
            mode = channel;
        }
        active = true;
        timer.restart();
    }

    Connections {
        target: audio
        function onChanged(channel) { root.showMode(channel); }
    }
    Connections {
        target: brightness
        function onChanged(value) { root.showMode("brightness"); }
    }

    Timer {
        id: timer
        interval: root.hideDelay
        repeat: false
        onTriggered: root.active = false
    }

    Behavior on progress {
        Components.Anim { motion: root.motion; type: Components.Anim.Emphasized }
    }

    OsdContent {
        id: card
        anchors.right: parent.right
        anchors.rightMargin: Wysun.Appearance.spaceXl
        anchors.verticalCenter: parent.verticalCenter
        width: Math.min(360, Math.max(260, root.width - Wysun.Appearance.spaceXl * 2))
        opacity: root.progress
        transform: Translate { x: (1 - root.progress) * Wysun.Appearance.spaceXl }
        motion: root.motion
        mode: root.mode
        volume: audio.volume
        muted: audio.muted
        sourceVolume: audio.sourceVolume
        sourceMuted: audio.sourceMuted
        brightness: brightness.value
        audioAvailable: audio.available
        brightnessAvailable: brightness.available
    }
}
