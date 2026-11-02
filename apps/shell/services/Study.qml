pragma Singleton

import QtQuick
import QtMultimedia
import Quickshell
import Quickshell.Io
import qs.utils
import "StudyPlan.js" as Plan

// Study mode (pomodoro). Owns the session, persists it in ${Paths.state}/study.json so a shell restart
// resumes it (same boot only: after a shutdown or reboot it is closed, not resumed), appends finished
// sessions to ${Paths.state}/study/sessions.jsonl and remembers the setup panel in ${Paths.config}/study.json.
// StudyBlocker hides and restores apps from `active`.
Singleton {
    id: root

    readonly property var defaults: ({duration: 120, rhythm: 25, blocked: ["brave-browser"], hideTime: true})

    property var session: null
    property var prefs: defaults
    property real now: Date.now()
    property var records: []
    // historyRecord of the session that just ended, for the summary.
    property var lastSummary: null
    property bool loaded
    // Kernel boot id: a saved session from another boot is closed instead of resumed.
    property string bootId
    property bool bootReady
    property bool storeReady
    property string savedText
    property real lastSave
    // Creates the blocker with the service, so parked windows are recovered even with no UI open.
    readonly property var blocker: StudyBlocker

    readonly property bool active: !!session && !session.done
    readonly property string phase: session ? session.phase : "done"
    readonly property bool paused: !!session && session.paused
    readonly property real progress: session ? Plan.progress(session, now) : 0
    readonly property int remainingMin: session ? Plan.remainingMin(session, now) : 0
    readonly property var week: Plan.weekTotals(records, now)

    signal phaseEnded(string from)
    signal distraction(string appName, string iconName)
    // Apps closed when the session started (names joined with commas).
    signal closedAtStart(string appNames, string iconName)
    signal requestSetup
    signal requestPill
    // Start straight away with the remembered setup (`wysun shell pomodoro start`).
    signal requestStart
    signal finished

    function summaryLine(duration: int, rhythm: int): string {
        return Plan.summaryLine(duration, rhythm);
    }

    // Display name of an app by window class: its desktop entry, else the class capitalised.
    function appName(cls: string): string {
        const lower = cls.toLowerCase();
        const apps = DesktopEntries.applications.values;
        const entry = DesktopEntries.heuristicLookup(cls) ?? apps.find(a => (a.startupClass || "").toLowerCase() === lower || a.id.toLowerCase() === lower);
        return entry?.name || cls.charAt(0).toUpperCase() + cls.slice(1);
    }

    function blockCount(duration: int, rhythm: int): var {
        return Plan.blockCount(duration, rhythm);
    }

    function toggle(): bool {
        if (active)
            requestPill();
        else
            requestSetup();
        return true;
    }

    function begin(config: var): void {
        savePrefs(config);
        lastSummary = null;
        now = Date.now();
        apply(Plan.start(config, now));
    }

    function startNext(): void {
        if (session)
            apply(Plan.startNext(session, Date.now()));
    }

    function skipToBreak(): void {
        if (session)
            apply(Plan.skipToBreak(session, Date.now()));
    }

    function togglePause(): void {
        if (session)
            apply(session.paused ? Plan.resume(session, Date.now()) : Plan.pause(session, Date.now()));
    }

    function countDistraction(appName: string, iconName: string): void {
        if (!active)
            return;
        const s = Object.assign({}, session);
        s.distractions += 1;
        session = s;
        save();
        distraction(appName, iconName);
    }

    // Hidden windows travel with the session so a restart can still give them back.
    function setHidden(list: var): void {
        if (!session)
            return;
        const s = Object.assign({}, session);
        s.hidden = list;
        session = s;
        save();
    }

    function finish(): void {
        if (!session)
            return;
        const t = Date.now();
        const ended = session.done ? session : Plan.stop(session, t);
        const record = Plan.historyRecord(ended, t);
        appendHistory(record);
        lastSummary = record;
        session = Object.assign({}, ended, {done: true});
        save();
        finished();
    }

    // Appended, never rewritten: the history may not have loaded yet (restart right after a session ended).
    function appendHistory(record: var): void {
        records = records.concat([record]);
        Quickshell.execDetached(["sh", "-c", 'mkdir -p "$(dirname "$1")" && printf "%s\\n" "$2" >> "$1"', "sh", history.path, JSON.stringify(record)]);
    }

    // The summary was closed: forget the finished session.
    function clear(): void {
        if (session && session.done) {
            session = null;
            save();
        }
    }

    function savePrefs(p: var): void {
        prefs = Object.assign({}, defaults, p);
        prefsFile.setText(JSON.stringify(prefs, null, 2));
    }

    function apply(next: var): void {
        const before = session ? session.phase : "";
        session = next;
        save();
        if (before && next.phase !== before && (before === "focus" || before === "break"))
            phaseEnded(before);
        if (next.done)
            finish();
    }

    // The file copy carries the boot it belongs to and when it was last seen alive (heartbeat).
    function save(): void {
        lastSave = Date.now();
        store.setText(JSON.stringify(session ? Object.assign({}, session, {boot: bootId, seenAt: lastSave}) : null));
    }

    // Runs once, when both the saved session and the boot id are known.
    function restore(): void {
        if (loaded || !storeReady || !bootReady)
            return;
        let saved = null;
        try {
            saved = JSON.parse(savedText);
        } catch (error) {}
        if (saved && !saved.done && saved.boot === bootId) {
            now = Date.now();
            session = Plan.tick(saved, now);
            if (session.done)
                finish();
        } else {
            session = null;
            if (saved && !saved.done)
                closeStale(saved);
        }
        loaded = true;
    }

    // A session left running when the PC was shut down: record it up to the last moment it was seen
    // (never the powered-off time) and drop it, without a summary or resuming.
    function closeStale(saved: var): void {
        const at = saved.seenAt || (saved.paused ? saved.pausedAt : saved.phaseStart);
        const record = Plan.historyRecord(Plan.stop(saved, at), at);
        appendHistory(record);
        save();
    }

    function chime(kind: string): void {
        (kind === "soft" ? softChime : endChime).play();
    }

    onPhaseEnded: from => chime(from === "focus" ? "end" : "soft")

    Timer {
        interval: 1000
        repeat: true
        running: root.active
        onTriggered: {
            root.now = Date.now();
            const next = Plan.tick(root.session, root.now);
            if (next.phase !== root.session.phase)
                root.apply(next);
            else if (root.now - root.lastSave >= 60000)
                root.save();
        }
    }

    SoundEffect {
        id: endChime

        source: Quickshell.shellPath("assets/sounds/study-chime.wav")
        volume: 0.6
    }

    SoundEffect {
        id: softChime

        source: Quickshell.shellPath("assets/sounds/study-chime-soft.wav")
        volume: 0.6
    }

    Process {
        running: true
        command: ["mkdir", "-p", `${Paths.state}/study`]
    }

    Process {
        running: true
        command: ["cat", "/proc/sys/kernel/random/boot_id"]
        stdout: StdioCollector {
            onStreamFinished: {
                root.bootId = text.trim();
                root.bootReady = true;
                root.restore();
            }
        }
        // Without a boot id every saved session counts as stale (closed, never resumed).
        onExited: code => {
            if (code !== 0) {
                root.bootReady = true;
                root.restore();
            }
        }
    }

    FileView {
        id: store

        path: `${Paths.state}/study.json`
        printErrors: false
        onLoaded: {
            root.savedText = text();
            root.storeReady = true;
            root.restore();
        }
        onLoadFailed: {
            root.storeReady = true;
            root.restore();
        }
    }

    FileView {
        id: history

        path: `${Paths.state}/study/sessions.jsonl`
        printErrors: false
        onLoaded: {
            const out = [];
            for (const line of text().split("\n")) {
                try {
                    if (line.trim())
                        out.push(JSON.parse(line));
                } catch (error) {}
            }
            root.records = out;
        }
    }

    FileView {
        id: prefsFile

        path: `${Paths.config}/study.json`
        printErrors: false
        onLoaded: {
            try {
                root.prefs = Object.assign({}, root.defaults, JSON.parse(text()));
            } catch (error) {
                root.prefs = root.defaults;
            }
        }
    }

    IpcHandler {
        target: "pomodoro"

        function toggle(): bool {
            return root.toggle();
        }

        function start(): bool {
            if (root.active)
                return false;
            root.requestStart();
            return true;
        }

        function pause(): bool {
            if (!root.active)
                return false;
            root.togglePause();
            return true;
        }

        function skip(): bool {
            if (!root.active)
                return false;
            if (root.phase === "focus")
                root.skipToBreak();
            else
                root.startNext();
            return true;
        }

        function stop(): bool {
            if (!root.active)
                return false;
            root.finish();
            return true;
        }

        function status(): string {
            const s = root.session;
            return JSON.stringify({active: root.active, phase: root.phase, paused: root.paused, block: s ? s.block : 0,
                                   blocks: s ? s.blocks : 0, progress: root.progress});
        }
    }
}
