import QtQuick
import Quickshell
import Quickshell.Io
import "Logic.js" as Logic

Scope {
    id: root
    readonly property string home: Quickshell.env("HOME") || ""
    readonly property string configHome: Quickshell.env("XDG_CONFIG_HOME") || home + "/.config"
    property var themeData: ({})
    property var themeSpec: ({})
    property var environment: ({})
    property var appearanceData: ({})
    property var nativeBarData: ({})
    // {style, variant}: environment override, then theme.json (new or legacy format).
    readonly property var themeSelection: Logic.selectTheme(themeSpec, themeData, Quickshell.env("WYSUN_THEME") || Quickshell.env("ORBIT_THEME"))
    readonly property string themeId: themeSelection.style + ":" + themeSelection.variant
    readonly property var appearance: Logic.appearance(appearanceData)
    readonly property var bar: Logic.barSettings(nativeBarData)

    function accept(text, field) {
        try { root[field] = Logic.object(text); }
        catch (error) { console.warn("Wysun: preferencias inválidas en " + field + "; se conserva el último valor válido."); return; }
        if (field === "themeSpec" || field === "themeData") publishTheme();
    }

    // Every shell widget reads the singleton, so a new selection repaints them all.
    function publishTheme() { Appearance.apply(themeSpec, Logic.selectTheme(themeSpec, themeData, Quickshell.env("WYSUN_THEME") || Quickshell.env("ORBIT_THEME"))); }
    Component.onCompleted: publishTheme()

    function reload() {
        themeSpecFile.reload(); themeFile.reload(); appearanceFile.reload();
        environmentFile.reload(); nativeBarFile.reload();
    }

    FileView {
        id: themeSpecFile
        path: Quickshell.shellPath("wysun_theme.json")
        blockLoading: true
        printErrors: false
        onLoaded: root.accept(text(), "themeSpec")
    }
    FileView {
        id: themeFile
        path: root.configHome + "/orbit/theme.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.accept(text(), "themeData")
    }
    FileView {
        id: appearanceFile
        path: root.configHome + "/orbit/appearance.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.accept(text(), "appearanceData")
    }
    FileView {
        id: environmentFile
        path: root.configHome + "/orbit/environment.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.accept(text(), "environment")
    }
    FileView {
        id: nativeBarFile
        path: root.configHome + "/orbit/hypr-bar.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.accept(text(), "nativeBarData")
    }
}
