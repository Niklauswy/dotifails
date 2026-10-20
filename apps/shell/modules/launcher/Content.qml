// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/Content.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "Logic.js" as Logic
FocusScope {
    id: root
    required property var launcher
    property alias query: search.text
    property alias searchItem: search
    property alias resultList: list
    readonly property var route: Logic.route(query)
    readonly property var rows: {
        var values;
        switch(route.mode) {
        case "apps": return launcher.apps.query(route.query).map(e => ({ kind: "apps", entry: e, name: e.name, description: e.genericName || e.comment || e.id }));
        case "actions": return launcher.actions.query(route.query).map(a => Object.assign({kind: "actions"}, a));
        case "calc":
            var result = Logic.calculate(route.query);
            return [{kind: "calc", name: result.valid ? result.value : "Expresión inválida", description: result.valid ? "Intro para copiar el resultado" : result.error, invalid: !result.valid, value: result.value}];
        case "scheme": values = launcher.schemes.query(route.query); break;
        case "variant": values = launcher.variants.query(route.query); break;
        case "wallpaper": values = launcher.schemes.wallpaperQuery(route.query); break;
        default: values = [];
        }
        return values.map(v => Object.assign({kind: route.mode, description: route.mode === "variant" ? "Material You desde el fondo actual" : "", current: route.mode === "scheme" && (v.id === "dynamic" ? Wysun.Appearance.dynamicActive : v.id === Wysun.Appearance.variant || v.id === Wysun.Appearance.style + ":" + Wysun.Appearance.variant)}, v));
    }
    onQueryChanged: launcher.errorMessage = ""
    function reset() { query = ""; search.forceActiveFocus(); }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.spaceL
        spacing: Wysun.Appearance.spaceS
        RowLayout {
            Layout.fillWidth: true
            Components.StyledText {
                Layout.fillWidth: true
                text: "Wysun"
                color: Wysun.Appearance.textStrong
                font.pixelSize: Wysun.Appearance.fontTitle
                Accessible.role: Accessible.Heading
            }
            Components.ActionButton {
                motion: root.launcher.motion
                implicitWidth: Wysun.Appearance.spaceXl * 2
                implicitHeight: Wysun.Appearance.spaceXl * 2
                glyph: "close"
                compact: true
                label: "Cerrar lanzador"
                onClicked: root.launcher.controller.close()
            }
        }
        ContentList {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            mode: root.route.mode
            rows: root.rows
            motion: root.launcher.motion
            onChosen: row => root.launcher.activate(row)
        }
        Components.StyledText {
            Layout.fillWidth: true
            visible: text.length > 0
            text: root.launcher.errorMessage || (root.launcher.schemes.busy ? "Aplicando cambios…" : root.launcher.schemes.loading ? "Consultando fondos…" : "")
            color: root.launcher.errorMessage ? Wysun.Appearance.danger : Wysun.Appearance.muted
            font.pixelSize: Wysun.Appearance.fontSmall
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            elide: Text.ElideRight
            Accessible.role: Accessible.AlertMessage
        }
        SearchBar {
            id: search
            objectName: "launcherSearch"
            Layout.fillWidth: true
            motion: root.launcher.motion
            onAccepted: list.accept()
            onMove: delta => list.move(delta)
            onDismiss: root.launcher.controller.close()
        }
        Components.StyledText {
            Layout.fillWidth: true
            text: "↑ ↓ elegir · Intro abrir · Esc cerrar"
            font.pixelSize: Wysun.Appearance.fontCaption
            color: Wysun.Appearance.muted
        }
    }
}
