// Adaptado de caelestia-dots/shell/services/Colours.qml (GPL-3.0), modificado
// para consumir el contrato Wysun de scheme.json y sus temas fijos. Fuente:
// caelestia-dots/shell, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import Quickshell
import Quickshell.Io
import "../" as Wysun
import "../Logic.js" as Logic

Scope {
    id: root

    readonly property string home: Quickshell.env("HOME") || ""
    readonly property string stateHome: Quickshell.env("XDG_STATE_HOME") || home + "/.local/state"
    readonly property string schemePath: stateHome + "/wysun/scheme.json"
    property var fallbackTokens: Wysun.Appearance.tokens
    property var roles: Logic.fixedSchemeRoles(fallbackTokens)
    property string name: ""
    property string mode: ""
    property string variant: ""
    property bool dynamic: false

    function useFallback() {
        var result = Logic.schemePalette(null, fallbackTokens);
        roles = result.roles;
        name = "";
        mode = "";
        variant = "";
        dynamic = false;
        Wysun.Appearance.applyScheme(roles, mode, false);
    }

    function accept(text) {
        try {
            var result = Logic.schemePalette(Logic.object(text), fallbackTokens);
            if (!result.valid) {
                console.warn("Wysun: scheme.json no cumple el contrato; se usa el tema fijo.");
                useFallback();
                return;
            }
            roles = result.roles;
            name = result.name;
            mode = result.mode;
            variant = result.variant;
            dynamic = true;
            Wysun.Appearance.applyScheme(roles, mode, true);
        } catch (error) {
            console.warn("Wysun: no se pudo leer scheme.json; se usa el tema fijo.");
            useFallback();
        }
    }

    function reload() { schemeFile.reload(); }

    onFallbackTokensChanged: if (!dynamic) useFallback()
    Component.onCompleted: reload()

    // FileView watches an existing file. Keep checking while the producer has
    // not created one yet so a later first scheme is picked up without restart.
    Timer {
        interval: 1000
        running: !root.dynamic
        repeat: true
        onTriggered: if (!root.dynamic) root.reload()
    }

    FileView {
        id: schemeFile
        path: root.schemePath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.accept(text())
        onLoadFailed: root.useFallback()
    }
}
