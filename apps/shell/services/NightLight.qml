pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import qs.utils

// Night light and software dimming on every output through hyprsunset (Hyprland's own CTM, no overlay).
// hyprsunset runs as a detached daemon (output to /dev/null, so it outlives a shell restart without dying
// on a closed pipe); the shell adopts a running one and drives it with `hyprctl hyprsunset`.
// Preferences live in ${Paths.config}/nightlight.json ({auto, start, end, temperature}); with `auto` it
// turns on between `start` and `end`. `toggle()` overrides the schedule until its next boundary.
// `gamma` (percent) is the extra dimming below the monitors' hardware minimum, set by Brightness.
Singleton {
    id: root

    readonly property var defaults: ({auto: true, start: "20:00", end: "07:00", temperature: 4000})

    property var prefs: defaults
    property bool available: true
    // Manual override (true/false) valid until `overrideUntil` (ms since epoch); null follows the schedule.
    property var override: null
    property real overrideUntil: 0
    property real now: Date.now()
    property int gamma: 100

    readonly property bool scheduled: prefs.auto && inWindow(new Date(now))
    readonly property bool active: override !== null && now < overrideUntil ? override : scheduled
    readonly property int temperature: Math.max(1000, Math.min(6500, prefs.temperature | 0))
    readonly property int clampedGamma: Math.max(20, Math.min(100, gamma))
    // What hyprsunset must show; applied whenever it changes.
    readonly property string wanted: `${active ? temperature : "identity"} ${clampedGamma}`

    function minutesOf(text: string): int {
        const parts = String(text).split(":");
        return (parseInt(parts[0], 10) || 0) * 60 + (parseInt(parts[1], 10) || 0);
    }

    function inWindow(date: var): bool {
        const start = minutesOf(prefs.start), end = minutesOf(prefs.end);
        const t = date.getHours() * 60 + date.getMinutes();
        return start <= end ? t >= start && t < end : t >= start || t < end;
    }

    // Next time the schedule flips (start or end), so a manual toggle lasts until then.
    function nextBoundary(): real {
        const base = new Date(now);
        let best = Infinity;
        for (const mark of [minutesOf(prefs.start), minutesOf(prefs.end)]) {
            const d = new Date(base);
            d.setHours(Math.floor(mark / 60), mark % 60, 0, 0);
            if (d.getTime() <= now)
                d.setDate(d.getDate() + 1);
            best = Math.min(best, d.getTime());
        }
        return best;
    }

    function set(on: bool): bool {
        now = Date.now();
        override = on === scheduled ? null : on;
        overrideUntil = override === null ? 0 : nextBoundary();
        return active;
    }

    function toggle(): bool {
        return set(!active);
    }

    function setPrefs(changes: var): void {
        prefs = Object.assign({}, prefs, changes);
        prefsFile.setText(JSON.stringify(prefs, null, 2));
    }

    function status(): string {
        return JSON.stringify({active, available, scheduled, temperature, gamma: clampedGamma, override, overrideUntil, prefs});
    }

    function apply(): void {
        applier.tries = 0;
        applier.restart();
    }

    onWantedChanged: apply()
    Component.onCompleted: apply()

    Timer {
        running: true
        repeat: true
        interval: 30000
        onTriggered: root.now = Date.now()
    }

    // Starts the daemon if none is running, then sets temperature and gamma; retries while its socket comes up.
    Timer {
        id: applier

        property int tries

        interval: tries === 0 ? 0 : 400
        onTriggered: {
            if (proc.running) {
                restart();
                return;
            }
            const temp = root.active ? `temperature ${root.temperature}` : "identity";
            proc.command = ["sh", "-c", "command -v hyprsunset >/dev/null || exit 127; "
                + "pgrep -u \"$(id -u)\" -x hyprsunset >/dev/null || { setsid hyprsunset -i >/dev/null 2>&1 & sleep 0.3; }; "
                + `hyprctl hyprsunset ${temp} | grep -qx ok && hyprctl hyprsunset gamma ${root.clampedGamma} | grep -qx ok`];
            proc.running = true;
        }
    }

    Process {
        id: proc

        onExited: code => {
            root.available = code !== 127;
            if (code !== 0 && code !== 127 && ++applier.tries < 10)
                applier.restart();
        }
    }

    FileView {
        id: prefsFile

        path: `${Paths.config}/nightlight.json`
        printErrors: false
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                root.prefs = Object.assign({}, root.defaults, JSON.parse(text()));
            } catch (error) {
                root.prefs = root.defaults;
            }
        }
    }

    IpcHandler {
        target: "nightlight"

        function toggle(): bool {
            return root.toggle();
        }
        function on(): bool {
            return root.set(true);
        }
        function off(): bool {
            return root.set(false);
        }
        function auto(enabled: bool): void {
            root.setPrefs({auto: enabled});
        }
        function schedule(start: string, end: string): void {
            root.setPrefs({start, end});
        }
        function temperature(kelvin: int): void {
            root.setPrefs({temperature: kelvin});
        }
        function status(): string {
            return root.status();
        }
    }
}
