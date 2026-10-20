// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/ContentList.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import QtQuick
import "../../" as Wysun
import "../../components" as Components
import "Logic.js" as Logic

Item {
    id: root
    property string mode: "apps"
    property var rows: []
    property var motion
    readonly property var currentList: mode === "wallpaper" ? wallpapers : apps
    signal chosen(var row)

    function move(delta) {
        currentList.currentIndex = Logic.nextIndex(currentList.currentIndex, delta, rows.length);
    }
    function accept() {
        var index = currentList.currentIndex;
        if (index >= 0 && index < rows.length) chosen(rows[index]);
    }

    AppList {
        id: apps
        anchors.fill: parent
        visible: root.mode !== "wallpaper"
        model: visible ? root.rows : []
        motion: root.motion
        onChosen: row => root.chosen(row)
    }
    WallpaperList {
        id: wallpapers
        anchors.fill: parent
        visible: root.mode === "wallpaper"
        model: visible ? root.rows : []
        motion: root.motion
        onChosen: row => root.chosen(row)
    }
    Components.StyledText {
        anchors.centerIn: parent
        width: parent.width - Wysun.Appearance.spaceXl
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        visible: root.rows.length === 0
        text: root.mode === "wallpaper"
            ? "No hay fondos. Añade imágenes a las carpetas de Ajustes o a ~/Pictures/Wallpapers."
            : "Sin resultados. Prueba otro nombre o escribe > para ver las acciones."
        color: Wysun.Appearance.muted
        font.pixelSize: Wysun.Appearance.fontBody
    }
}
