pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import "ProcLogic.js" as Logic

// Live figures for the launcher's process pane: while a running app or a kill row is selected, one `ps` per second
// gives its CPU (% of one core, from cumulative CPU time), memory and process count, plus a minute of history for
// the sparkline. Idle otherwise.
Singleton {
    id: root

    property var tracked: null            // {key, pids?, name?}
    property var current: ({cpu: 0, memory: 0, count: 0})
    property var history: []
    property var previous: null
    property var table: null             // latest parsed `ps`; only freshTable() hands it out
    property real stamp: 0

    function track(row: var): void {
        const key = row?.key ?? "";
        if (!row || !["proc", "kill"].includes(row.kind)) {
            tracked = null;
            table = null;
            previous = null;
            stamp = 0;
            return;
        }
        if (tracked?.key !== key) {
            history = [];
            current = {cpu: 0, memory: 0, count: 0};
        }
        tracked = row.kind === "proc" ? {key: key, pids: row.pids} : {key: key, name: row.name};
        sample();
    }

    function sample(): void {
        ps.running = false;
        ps.running = true;
    }

    // The latest sample, only while it is at most `maxAgeSeconds` old: a stale table may hold reused pids.
    function freshTable(maxAgeSeconds: real): var {
        return Logic.isFresh(stamp, Date.now() / 1000, maxAgeSeconds) ? table : null;
    }

    Timer {
        interval: 1000
        running: root.tracked !== null
        repeat: true
        onTriggered: root.sample()
    }

    Process {
        id: ps

        command: ["ps", "-eo", "pid=,ppid=,cputimes=,rss=,comm="]
        stdout: StdioCollector {
            onStreamFinished: {
                const t = root.tracked;
                if (!t)
                    return;
                const now = Date.now() / 1000;
                const table = Logic.parsePs(text);
                root.table = table;
                const rates = Logic.withRates(table, root.previous, root.stamp ? now - root.stamp : 0);
                root.previous = table;
                root.stamp = now;
                const s = t.pids ? Logic.aggregate(rates, t.pids) : Logic.byName(rates, t.name);
                root.current = s;
                root.history = Logic.pushSample(root.history, s.cpu);
            }
        }
    }
}
