// Runtime probe for the provider bridge (run by tests/test_qml_runtime.py with a
// fixture file: no D-Bus, no subprocess other than the Python provider, no device).
// It lives beside shell.qml so Quickshell treats this folder as the config root.
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import "services" as Services

ShellRoot {
    Services.DesktopServices {
        id: hub
        domains: "bluetooth,notifications"
        active: true
        fixture: true
        fixturePath: Quickshell.env("WYSUN_PROBE_FIXTURE")
        onActionDone: name => console.info("PROBE_ACTION", name, hub.error === "" ? "ok" : hub.error)
    }
    Timer {
        interval: 1200
        running: true
        onTriggered: {
            console.info("PROBE_SNAPSHOT", hub.error === "" ? "ok" : hub.error, hub.domain("bluetooth").enabled,
                hub.domain("bluetooth").devices.length, hub.domain("notifications").items.length,
                hub.domain("session").available);
            hub.act("bluetooth-toggle");
        }
    }
    Timer {
        interval: 2400
        running: true
        onTriggered: hub.act("bluetooth-connect", "00:00:00:00:00:00")
    }
    Timer {
        interval: 3600
        running: true
        onTriggered: {
            console.info("PROBE_REJECTED", hub.error);
            hub.active = false;
            console.info("PROBE_BUSY_AFTER_CLOSE", hub.busy, hub.act("bluetooth-toggle"));
            Qt.quit();
        }
    }
}
