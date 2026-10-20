// Adaptado de caelestia-dots/shell/modules/bar/popouts/Battery.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// The provider reads /sys/class/power_supply once when the panel opens.
import QtQuick

QtObject {
    required property var hub

    readonly property var state: hub ? (hub.states.battery || ({})) : ({})
    readonly property bool available: state.available === true
    readonly property string error: state.error || "No hay batería disponible"
    readonly property int percent: state.percent !== undefined ? state.percent : 0
    readonly property string status: state.status || "Estado no disponible"
    readonly property bool charging: status === "Cargando"
    readonly property string glyph: percent < 15 ? "battery_alert" : "battery_full"
}
