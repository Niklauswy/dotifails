// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: services/NotifData.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
QtObject {
    property var entry: ({})
    readonly property string notificationId: String(entry.id || "")
    readonly property string summary: entry.summary || "Aviso"
    readonly property string body: entry.body || ""
    readonly property string appName: entry.appName || "Aplicación"
    readonly property bool critical: ["critical", "2"].indexOf(String(entry.urgency)) >= 0
    // Dunst owns lifetime, persistence and app actions. History is inert data.
    readonly property var actions: []
}
