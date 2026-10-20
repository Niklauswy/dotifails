// Offscreen gallery for the Wysun dashboard and the popout morph. It uses a
// FloatingWindow (never a PanelWindow or a compositor) and fixture providers, so
// it runs with a temporary HOME and no MPRIS, /proc sampling or Hyprland.
// Controlled by environment variables read by tests/test_dashboard_qml.py.
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import "services" as Services
import "modules/popouts" as PopoutModule

ShellRoot {
    id: root
    readonly property string fixture: Quickshell.env("WYSUN_GALLERY_FIXTURE") || "full"
    readonly property string scenario: Quickshell.env("WYSUN_GALLERY_SCENARIO") || "capture"
    readonly property int tab: parseInt(Quickshell.env("WYSUN_GALLERY_TAB") || "0")
    // "0,1,2,3": capture each tab in turn; "%t" in the output path becomes the tab index.
    readonly property var tabs: (Quickshell.env("WYSUN_GALLERY_TABS") || "").split(",").filter(function(t) { return t !== ""; }).map(Number)
    property int tabStep: 0
    readonly property bool live: Quickshell.env("WYSUN_GALLERY_LIVE") === "1"
    readonly property bool reduced: Quickshell.env("WYSUN_GALLERY_REDUCED") === "1"
    readonly property string output: Quickshell.env("WYSUN_GALLERY_OUT") || "/tmp/wysun-dashboard.png"
    property var samples: []

    Preferences { id: prefs }
    Services.Colours { id: colours }
    Motion { id: motion; reducedMotion: root.reduced }
    FontLoader {
        source: Quickshell.shellPath("assets/fonts/Rubik-Variable.ttf")
        onStatusChanged: if (status === FontLoader.Ready) Appearance.refreshFonts()
    }
    FontLoader {
        source: Quickshell.shellPath("assets/fonts/MaterialSymbolsRounded.ttf")
        onStatusChanged: if (status === FontLoader.Ready) Appearance.refreshFonts()
    }

    QtObject {
        id: controller
        property string surface: "dashboard"
        property string lastLaunch: ""
        property int closeCount: 0
        function launch(command) { lastLaunch = command; return true; }
        function close() { closeCount++; }
        function activateWindow(window) { return true; }
    }

    DashboardFixtures { id: fixtures; empty: root.fixture === "empty" }

    PopoutModule.PopoutState {
        id: popup
        motion: motion
        requested: false
    }

    FloatingWindow {
        id: win
        visible: true
        title: "Galería del panel de Wysun"
        implicitWidth: 1280
        implicitHeight: 800
        color: Appearance.well

        Item {
            id: scene
            anchors.fill: parent
            readonly property var target: Qt.rect((width - 860) / 2, (height - 600) / 2, 860, 600)
            readonly property var origin: Qt.rect(24, 120, 72, 64)

            PopoutModule.Wrapper {
                id: wrapper
                motion: motion
                progress: popup.progress
                originRect: scene.origin
                targetRect: scene.target
                contentOpacity: root.reduced ? 1 : Math.max(0, Math.min(1, (progress - 0.15) / 0.6))

                PopoutModule.PopoutCard {
                    id: card
                    anchors.fill: parent
                    framed: false
                    controller: controller
                    motion: motion
                    monitorName: "DP-1"
                    live: root.live
                    providers: fixtures.providers
                    dashboardTab: root.tabs.length ? root.tabs[0] : root.tab
                }
            }
        }
    }

    // Visible text of the card, so tests can assert what the user would read.
    function texts(item, out) {
        if (!item || item.visible === false) return out;
        if (item.text !== undefined && item.font !== undefined && String(item.text) !== "") out.push(String(item.text));
        var kids = item.children || [];
        for (var i = 0; i < kids.length; i++) texts(kids[i], out);
        return out;
    }

    function finish(code) {
        console.info("WYSUN_GALLERY_DONE", code);
        Qt.quit();
    }

    function grab(tag, then) {
        var path = root.output.replace("%t", String(card.dashboardTab));
        var started = scene.grabToImage(function(result) {
            console.info("WYSUN_GALLERY_TEXTS", JSON.stringify(root.texts(card, [])));
            var providers = card.activeProviders;
            console.info("WYSUN_GALLERY_PROVIDERS", providers ? JSON.stringify({
                cpu: providers.metrics.cpu, memory: providers.metrics.memory, storage: providers.metrics.storage,
                media: providers.media ? { title: providers.media.title, players: providers.media.players.length } : null,
                workspaces: providers.workspaces.length, windows: providers.windows.length }) : "none");
            console.info("WYSUN_GALLERY_CAPTURE", tag, result.saveToFile(path), Appearance.style, Appearance.variant, colours.dynamic);
            if (then) then();
        });
        console.info("WYSUN_GALLERY_GRAB_REQUEST", started, scene.width, scene.height, win.visible);
    }

    // Per-frame progress sample, used to prove an interrupted transition has no jump.
    FrameAnimation {
        running: root.scenario === "interrupt"
        onTriggered: root.samples.push(Math.round(popup.progress * 1000) / 1000)
    }

    Timer {
        id: start
        interval: 700
        running: true
        onTriggered: {
            console.info("WYSUN_GALLERY_START", root.scenario, root.fixture, root.tab, root.reduced);
            popup.requested = true;
            if (root.scenario === "interrupt") close1.start();
            else settle.start();
        }
    }
    Timer {
        id: settle
        interval: root.live ? 3500 : (root.reduced ? 400 : 1500)
        onTriggered: root.grab("open", function() { if (root.tabs.length > 1) nextTab.start(); else root.finish(0); })
    }
    Timer {
        id: nextTab
        interval: 700
        onTriggered: {
            root.tabStep++;
            card.dashboardTab = root.tabs[root.tabStep];
            root.grab("tab", function() { if (root.tabStep + 1 < root.tabs.length) nextTab.start(); else root.finish(0); });
        }
    }
    Timer { id: close1; interval: 140; onTriggered: { console.info("WYSUN_GALLERY_CLOSE", popup.progress); popup.requested = false; reopen.start(); } }
    Timer { id: reopen; interval: 90; onTriggered: { console.info("WYSUN_GALLERY_REOPEN", popup.progress); popup.requested = true; done.start(); } }
    Timer {
        id: done
        interval: 1500
        onTriggered: {
            console.info("WYSUN_GALLERY_SAMPLES", JSON.stringify(root.samples), popup.progress, popup.phase);
            root.grab("interrupt", function() { root.finish(0); });
        }
    }
    Timer { interval: 20000; running: true; onTriggered: { console.warn("WYSUN_GALLERY_TIMEOUT"); Qt.quit(); } }
}
