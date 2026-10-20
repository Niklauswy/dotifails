// Adaptado de caelestia-dots/shell/modules/osd/{Wrapper,Content}.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// One OSD controller for the whole session. It observes the default PipeWire
// nodes and the sysfs backlight (no polling), so every volume, mute and
// microphone change shows it, including the existing multimedia keys, which
// are not touched. Values present at start-up are ignored.
import QtQuick
import Quickshell
import Quickshell.Hyprland
import "../../services" as Services

Scope {
    id: root

    required property var motion
    property bool active: false
    property string mode: "volume"
    property string screenName: ""
    readonly property int hideDelay: 1600

    readonly property var audio: audioService
    readonly property var brightness: brightnessService

    Services.Audio { id: audioService }
    Services.Brightness { id: brightnessService }

    function show(channel) {
        if (channel === "brightness") {
            if (!brightnessService.available) return;
        } else if (channel === "source-volume" || channel === "source-mute") {
            if (!audioService.sourceAvailable) return;
        } else if (!audioService.available) {
            return;
        }
        var focused = Hyprland.focusedMonitor?.name || "";
        var known = Quickshell.screens.some(function(screen) { return screen.name === focused; });
        screenName = known ? focused : (Quickshell.screens.length > 0 ? Quickshell.screens[0].name : "");
        mode = channel;
        active = true;
        timer.restart();
    }

    Connections {
        target: audioService
        function onChanged(channel) { root.show(channel); }
    }
    Connections {
        target: brightnessService
        function onChanged(value) { root.show("brightness"); }
    }

    Timer {
        id: timer
        interval: root.hideDelay
        repeat: false
        onTriggered: root.active = false
    }

    Variants {
        model: Quickshell.screens
        OsdHost { osd: root; motion: root.motion }
    }
}
