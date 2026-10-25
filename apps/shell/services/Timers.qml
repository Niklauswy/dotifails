pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import qs.utils

// Countdowns started from the launcher ("timer 10m tea"). A transient systemd timer does the ringing, so
// it still rings if the shell restarts; this service only remembers what is running (for the utilities
// card) and ticks while there is something to show: with no timer active nothing runs at all.
Singleton {
    id: root

    // [{unit, end (ms since epoch), seconds, label}], soonest first.
    property var timers: []
    property real now: Date.now()
    readonly property bool active: timers.length > 0

    // Rings: a notification that stays until clicked (the shell keeps "x-wysun-sticky" ones on screen). No sound.
    readonly property string ringScript: 'notify-send -a Wysun -u critical -i alarm-clock -h int:x-wysun-sticky:1 -- "Timer finished" "$1"'

    function start(seconds: int, label: string): void {
        const stamp = Date.now();
        const unit = `wysun-timer-${stamp}`;
        const text = label || "Time is up";
        Quickshell.execDetached(["systemd-run", "--user", "--quiet", `--unit=${unit}`, `--on-active=${seconds}`, "--timer-property=AccuracySec=1s",
                                 "--description=Wysun timer", "sh", "-c", ringScript, "sh", text]);
        timers = timers.concat([{unit: unit, end: stamp + seconds * 1000, seconds: seconds, label: label}]).sort((a, b) => a.end - b.end);
        now = stamp;
        save();
    }

    function cancel(unit: string): void {
        Quickshell.execDetached(["systemctl", "--user", "stop", `${unit}.timer`, `${unit}.service`]);
        timers = timers.filter(t => t.unit !== unit);
        save();
    }

    function remaining(timer: var): int {
        return Math.max(0, Math.ceil((timer.end - now) / 1000));
    }

    // 8:05, or 1:02:03 from an hour up.
    function format(seconds: int): string {
        const h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60), s = seconds % 60;
        const two = n => (n < 10 ? "0" : "") + n;
        return h > 0 ? `${h}:${two(m)}:${two(s)}` : `${m}:${two(s)}`;
    }

    function save(): void {
        store.setText(JSON.stringify(timers));
    }

    // Timers that ran out are done (systemd rings them); drop them from the list.
    function prune(): void {
        now = Date.now();
        const live = timers.filter(t => t.end > now);
        if (live.length !== timers.length) {
            timers = live;
            save();
        }
    }

    Timer {
        interval: 1000
        repeat: true
        running: root.active
        onTriggered: root.prune()
    }

    // What was running when the shell last stopped.
    FileView {
        id: store

        path: `${Paths.state}/timers.json`
        printErrors: false
        onLoaded: {
            try {
                const saved = JSON.parse(text());
                root.timers = Array.isArray(saved) ? saved.filter(t => t.end > Date.now()) : [];
            } catch (error) {
                root.timers = [];
            }
            root.now = Date.now();
        }
    }
}
