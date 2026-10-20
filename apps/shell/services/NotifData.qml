// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: services/NotifData.qml (commit 507d66285e9d9fde9330adc64159cfdebb28c19a).
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// Dunst owns lifetime, persistence and app actions. This is presentation only.
import QtQuick

QtObject {
    property var entry: ({})

    readonly property string notificationId: String(entry.id || "")
    readonly property string summary: entry.summary || "Aviso"
    readonly property string body: entry.body || ""
    readonly property string appName: entry.appName || "Aplicación"
    readonly property string urgency: String(entry.urgency || "normal")
    readonly property bool critical: ["critical", "2"].indexOf(urgency) >= 0
    readonly property string urgencyLabel: critical ? "Crítico" : (["low", "0"].indexOf(urgency) >= 0 ? "Baja" : "Normal")
    readonly property string glyph: critical ? "notifications_active" : "notifications"
    readonly property bool hasBody: body.length > 0
    readonly property var actions: []
}
