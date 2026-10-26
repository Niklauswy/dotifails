// Scroll benchmark of the lists page (--bench): animates the 10 000-row ListView's contentY linearly and times
// every frameSwapped, like the phase-0 spike's Bench. Reports fps, frame-time percentiles and slow frames.
import QtQuick

Item {
    id: root

    property var window
    property Flickable view
    property bool recording
    property var stamps: []
    property var results: ({})
    property int phaseIndex: -1
    readonly property var phases: [
        {name: "list_fling", distance: 20000, ms: 4000},
        {name: "list_full", distance: -1, ms: 8000}
    ]

    signal finished(var result)
    signal needsList

    function start() {
        needsList();
        settle.start();
    }

    function phase(i) {
        if (i >= phases.length) {
            finished(results);
            return;
        }
        phaseIndex = i;
        const p = phases[i];
        view.contentY = 0;
        const end = p.distance < 0 ? Math.max(0, view.contentHeight - view.height) : Math.min(p.distance, view.contentHeight - view.height);
        anim.from = 0;
        anim.to = end;
        anim.duration = p.ms;
        stamps = [];
        recording = true;
        anim.start();
    }

    function summarize(name, distance) {
        const s = stamps;
        const iv = [];
        for (let k = 1; k < s.length; ++k)
            iv.push(s[k] - s[k - 1]);
        iv.sort((a, b) => a - b);
        const pct = q => iv.length ? iv[Math.min(iv.length - 1, Math.floor(q * iv.length))] : 0;
        results[name] = {
            frames: s.length,
            fps: +(1000 * (s.length - 1) / Math.max(1, s[s.length - 1] - s[0])).toFixed(1),
            p50: pct(0.5),
            p95: pct(0.95),
            max: iv.length ? iv[iv.length - 1] : 0,
            over25ms: iv.filter(v => v > 25).length,
            px: Math.round(distance)
        };
    }

    Timer {
        id: settle

        interval: 1500
        onTriggered: root.view && root.view.contentHeight > 0 ? root.phase(0) : restart()
    }

    Connections {
        target: root.window

        function onFrameSwapped() {
            if (root.recording)
                root.stamps.push(Date.now());
        }
    }

    NumberAnimation {
        id: anim

        target: root.view
        property: "contentY"
        easing.type: Easing.Linear
        onFinished: {
            root.recording = false;
            root.summarize(root.phases[root.phaseIndex].name, to);
            root.phase(root.phaseIndex + 1);
        }
    }
}
