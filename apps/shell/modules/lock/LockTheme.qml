// Carga mínima de tokens para el proceso de bloqueo aislado (LockShell.qml).
// El proceso de bloqueo no instancia Preferences completo: solo necesita la
// especificación wysun_theme.json, la selección theme.json y appearance.json.
// La selección dinámica scheme.json llega por services/Colours.qml, igual que
// en la shell, sin crear un segundo productor de color.
import QtQuick
import Quickshell
import Quickshell.Io
import "../../" as Wysun
import "../../Logic.js" as Logic
import "../../config/Paths.js" as Paths

Scope {
    id: root

    required property string shellRoot
    readonly property string home: Quickshell.env("HOME") || ""
    readonly property string configHome: Paths.configHome(Quickshell.env("XDG_CONFIG_HOME"), home)
    property var spec: ({})
    property var selectionData: ({})
    property var appearanceData: ({})
    readonly property var selection: Logic.selectTheme(spec, selectionData,
        Quickshell.env("WYSUN_THEME") || Quickshell.env("ORBIT_THEME"))
    readonly property var appearance: Logic.appearance(appearanceData)

    function publish() {
        if (!spec || typeof spec !== "object" || Array.isArray(spec)) return;
        Wysun.Appearance.apply(spec, selection);
    }
    onSelectionChanged: publish()
    onSpecChanged: publish()
    onShellRootChanged: specFile.reload()

    FileView {
        id: specFile
        path: root.shellRoot + "/wysun_theme.json"
        printErrors: false
        onLoaded: { try { root.spec = Logic.object(text()); } catch (error) { console.warn("Wysun Lock: wysun_theme.json inválido"); } }
        Component.onCompleted: reload()
    }
    FileView {
        id: themeFile
        path: Paths.orbitFile(root.configHome, "theme.json")
        printErrors: false
        onLoaded: { try { root.selectionData = Logic.object(text()); } catch (error) { root.selectionData = ({}); } }
        Component.onCompleted: reload()
    }
    FileView {
        id: appearanceFile
        path: Paths.orbitFile(root.configHome, "appearance.json")
        printErrors: false
        onLoaded: { try { root.appearanceData = Logic.object(text()); } catch (error) { root.appearanceData = ({}); } }
        Component.onCompleted: reload()
    }
}
