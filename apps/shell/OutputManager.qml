import QtQuick
import Quickshell
import Quickshell.Hyprland
import "Logic.js" as Logic

QtObject {
    readonly property var screens: Quickshell.screens

    function screenByName(name) {
        return screens.find(function(screen) { return screen.name === name; }) || null;
    }

    function monitorFor(screen) { return screen ? Hyprland.monitorFor(screen) : null; }

    function isFullscreen(screen) {
        var monitor = monitorFor(screen);
        return monitor?.activeWorkspace?.hasFullscreen === true;
    }

    function trayOwner(preferences) {
        return Logic.trayMonitor(preferences.environment, screens, preferences.nativeBarData);
    }
}
