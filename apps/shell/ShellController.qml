import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "Logic.js" as Logic

Scope {
    id: root
    required property var preferences
    required property var state
    property var resources: null
    property string errorMessage: ""
    property string requestedCommand: ""
    property bool commandStarted: false
    property var commandExitCode: null
    property int commandAttempts: 0
    property string commandResult: "idle"
    property int secondaryClickCount: 0
    property bool secondaryClickAccepted: false
    property string secondaryClickSurface: ""
    readonly property string surface: state.surface
    readonly property string screenName: state.screenName
    readonly property var popupScreen: Quickshell.screens.find(s => s.name === state.screenName) || null
    readonly property bool opened: state.opened && popupScreen !== null
    readonly property bool busy: application.running

    function close() { state.close(); }

    function supportsSurface(kind) {
        return ["test", "dashboard", "launcher", "menu", "windows", "session"].indexOf(kind) >= 0;
    }

    function show(kind, name, anchorX, anchorY, focusItem) {
        if (!supportsSurface(kind)) return false;
        var target = Logic.popupScreen(Quickshell.screens, name || Hyprland.focusedMonitor?.name);
        if (!target) return false;
        errorMessage = "";
        state.open(kind, target.name,
            typeof anchorX === "number" && isFinite(anchorX) ? anchorX : Appearance.railWidth / 2,
            typeof anchorY === "number" && isFinite(anchorY) ? anchorY : target.height / 2,
            focusItem ? "rail-logo" : "", focusItem || null);
        return true;
    }

    function toggle(kind, name, anchorX, anchorY, focusItem) {
        if (!supportsSurface(kind)) return false;
        if (state.opened && (!name || name === state.screenName)) { close(); return true; }
        return show(kind, name, anchorX, anchorY, focusItem);
    }

    function secondaryClick(name) {
        secondaryClickCount++;
        secondaryClickAccepted = toggle("menu", name);
        // Preserve the immediate result even if focus handling closes it later.
        secondaryClickSurface = surface;
        return secondaryClickAccepted;
    }

    function launch(command) {
        if (!Logic.allowedCommand(command)) return false;
        requestedCommand = command;
        commandAttempts++;
        if (busy) { commandResult = "busy"; return false; }
        commandResult = "starting";
        commandStarted = false;
        commandExitCode = null;
        errorMessage = "";
        // A public, short-lived CLI dispatch; Python remains owner of app state.
        application.command = ["wysun", command];
        application.running = true;
        startCheck.restart();
        return true;
    }

    // The theme selector lives in Wysun Ajustes; the shell only asks for it.
    function openThemeSettings() {
        if (themeSettings.running) return false;
        themeSettings.command = ["wysun", "settings", "theme"];
        themeSettings.running = true;
        close();
        return true;
    }

    function activateWindow(window) {
        if (!window || !window.wayland) return false;
        close();
        window.wayland.activate();
        return true;
    }

    Process {
        id: themeSettings
        stdout: SplitParser { onRead: function(data) {} }
        stderr: SplitParser { onRead: function(data) {} }
    }
    Process {
        id: application
        stdout: SplitParser { onRead: function(data) {} }
        stderr: SplitParser { onRead: function(data) {} }
        onStarted: { root.commandStarted = true; root.commandResult = "started"; root.close(); }
        onExited: (code, status) => {
            root.commandExitCode = code;
            root.commandResult = code === 0 && status === 0 ? "exited" : "failed";
            if (code !== 0 || status !== 0) {
                root.show("menu", root.screenName);
                root.errorMessage = "No se pudo abrir " + root.requestedCommand + " (código " + code + "). Revisa wysun doctor.";
            }
        }
    }
    Timer {
        id: startCheck
        interval: 1000
        repeat: false
        onTriggered: {
            if (!root.commandStarted)
                root.errorMessage = "No se encuentra el comando público wysun. Revisa la instalación de la sesión.";
        }
    }
    Connections {
        target: Quickshell
        function onScreensChanged() {
            if (!Quickshell.screens.some(s => s.name === root.state.screenName)) root.close();
        }
    }
    IpcHandler {
        target: "wysunShell"
        function toggle(surface: string): bool { return root.toggle(surface, ""); }
        function open(surface: string): bool { return root.show(surface, ""); }
        function close(): void { root.close(); }
        function reloadPreferences(): void { root.preferences.reload(); }
        function theme(): string { return JSON.stringify({ style: Appearance.style, variant: Appearance.variant, name: Appearance.name }); }
        function openThemeSettings(): bool { return root.openThemeSettings(); }
        function status(): string {
            // Do not expose private window titles, notification bodies or files.
            return JSON.stringify({ version: 1, surface: root.surface, monitor: root.screenName,
                screens: Quickshell.screens.map(s => s.name), theme: root.preferences.themeId,
                commandFailed: root.errorMessage !== "",
                lastCommand: root.requestedCommand, commandStarted: root.commandStarted,
                commandRunning: root.busy, commandExitCode: root.commandExitCode,
                commandAttempts: root.commandAttempts, commandResult: root.commandResult,
                secondaryClickCount: root.secondaryClickCount,
                secondaryClickAccepted: root.secondaryClickAccepted,
                secondaryClickSurface: root.secondaryClickSurface,
                phase: root.state.phase, returnFocus: root.state.returnFocus,
                resources: root.resources ? { enabled: root.resources.enabled,
                    cpu: root.resources.sample?.percent ?? null, memory: root.resources.memory } : null,
                nativeBar: Object.keys(root.preferences.nativeBarData).length > 0,
                bar: root.preferences.bar,
                windowCount: Hyprland.toplevels.values.length, workspaceCount: Hyprland.workspaces.values.length,
                fullscreenMonitors: Hyprland.monitors.values.filter(m => m.activeWorkspace?.hasFullscreen).map(m => m.name) });
        }
    }
}
