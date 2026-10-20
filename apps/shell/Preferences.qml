import QtQuick
import Quickshell
import Quickshell.Io
import "Logic.js" as Logic

Scope {
    id: root
    readonly property string home: Quickshell.env("HOME") || ""
    readonly property string configHome: Quickshell.env("XDG_CONFIG_HOME") || home + "/.config"
    property var themeData: ({})
    property var environment: ({})
    property var appearanceData: ({})
    property var nativeBarData: ({})
    readonly property string themeId: Logic.themeKey(Quickshell.env("WYSUN_THEME") || Quickshell.env("ORBIT_THEME") || themeData.id)
    readonly property var palette: Logic.themes[themeId]
    readonly property var appearance: Logic.appearance(appearanceData)
    readonly property var bar: Logic.barSettings(nativeBarData)

    function accept(text, field) {
        try { root[field] = Logic.object(text); }
        catch (error) { console.warn("Wysun: preferencias inválidas en " + field + "; se conserva el último valor válido."); }
    }

    function reload() {
        themeFile.reload(); appearanceFile.reload();
        environmentFile.reload(); nativeBarFile.reload();
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
