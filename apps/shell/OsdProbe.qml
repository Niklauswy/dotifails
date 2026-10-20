// Runtime probe for the OSD sources (run by tests/test_qml_runtime.py;
// it lives beside shell.qml so Quickshell treats this folder as the config root with an
// offscreen Qt platform, a fake backlight tree and a brightnessctl stub; it never
// touches PipeWire, Hyprland or real devices).
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import "modules/osd" as OsdModule

ShellRoot {
    Motion { id: motion; reducedMotion: true }
    OsdModule.OsdState { id: osd }

    Connections {
        target: osd.brightness
        function onChanged(value) { console.info("PROBE_CHANGED", Math.round(value * 100)); }
    }
    Connections {
        target: osd
        function onActiveChanged() { console.info("PROBE_OSD", osd.active, osd.mode); }
    }
    Timer {
        interval: 900
        running: true
        onTriggered: console.info("PROBE_AUDIO", osd.audio.available, osd.audio.sourceAvailable, osd.audio.error)
    }
    Timer {
        interval: 900
        running: true
        onTriggered: console.info("PROBE_READY", osd.brightness.available, osd.brightness.device,
            Math.round(osd.brightness.value * 100), osd.brightness.error, osd.active)
    }
    Timer {
        interval: Number(Quickshell.env("WYSUN_PROBE_SECONDS") || 6) * 1000
        running: true
        onTriggered: { console.info("PROBE_DONE", osd.active); Qt.quit(); }
    }
}
