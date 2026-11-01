pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Wysun.Config
import qs.services

// Study mode UI: one overlay window per screen. The setup panel, the full-screen entry, the pill, its cards
// and the summary are a single surface on the screen where the session started; the others only show
// the full-screen entry and the halo. Everything follows `mode`.
Scope {
    id: root

    // hidden | setup | takeover | study | summary
    property string mode: "hidden"
    property string pillScreen: ""
    property var pending: null
    // Geometry changes use the slow spatial curve while growing to full screen and collapsing to the pill.
    property bool slowMorph
    // Bumped to run the light around the screen edge once; `shortSweep` for the lap after a break.
    property int sweepTick
    property bool shortSweep
    // The pill shows the minutes while this is on (eye button).
    property bool revealTime
    // The pill took the keyboard (Super+N during a session): Space pauses, → skips, X asks to finish.
    property bool keyboard

    signal pillRequested

    function focusedScreen(): string {
        return Hypr.focusedMonitor?.name ?? Quickshell.screens[0]?.name ?? "";
    }

    function openSetup(): void {
        if (Study.active || mode === "takeover")
            return;
        if (mode === "setup") {
            mode = "hidden";
            return;
        }
        pillScreen = focusedScreen();
        mode = "setup";
    }

    function close(): void {
        if (mode === "setup") {
            mode = "hidden";
        } else if (mode === "summary") {
            mode = "hidden";
            Study.clear();
        }
    }

    function start(config: var): void {
        pending = config;
        revealTime = false;
        slowMorph = true;
        mode = "takeover";
        beginTimer.restart();
        collapseTimer.restart();
    }

    function sweep(quick: bool): void {
        shortSweep = quick;
        sweepTick++;
    }

    // The apps go away once the screen is covered.
    Timer {
        id: beginTimer

        interval: Tokens.anim.durations.expressiveSlowSpatial
        onTriggered: Study.begin(root.pending)
    }

    // Full screen holds for a moment, then collapses into the pill and the light runs around the edge.
    Timer {
        id: collapseTimer

        interval: Tokens.anim.durations.expressiveSlowSpatial + Tokens.anim.durations.extraLarge + Tokens.anim.durations.large
        onTriggered: {
            root.mode = "study";
            sweepTimer.restart();
        }
    }

    Timer {
        id: sweepTimer

        interval: Tokens.anim.durations.expressiveSlowSpatial
        onTriggered: {
            root.slowMorph = false;
            root.sweep(false);
        }
    }

    Connections {
        target: Study

        function onRequestSetup(): void {
            root.openSetup();
        }

        function onRequestStart(): void {
            if (Study.active || root.mode === "takeover")
                return;
            root.pillScreen = root.focusedScreen();
            root.start(Study.prefs);
        }

        function onRequestPill(): void {
            root.pillRequested();
        }

        function onFinished(): void {
            if (!root.pillScreen)
                root.pillScreen = root.focusedScreen();
            root.mode = "summary";
        }

        // A session resumed after a shell restart shows its pill straight away.
        function onActiveChanged(): void {
            if (Study.active && root.mode === "hidden" && !resumeTimer.running) {
                root.pillScreen = root.focusedScreen();
                root.mode = "study";
            }
        }
    }

    // The session may have been loaded before this module existed.
    // Hyprland's focused monitor arrives a moment after start-up: wait for it.
    Component.onCompleted: resumeTimer.start()

    Timer {
        id: resumeTimer

        interval: Tokens.anim.durations.normal
        onTriggered: {
            if (Study.active && root.mode === "hidden") {
                root.pillScreen = root.focusedScreen();
                root.mode = "study";
            }
        }
    }

    Variants {
        model: Quickshell.screens

        StudyWindow {
            ui: root
        }
    }
}
