// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Performance.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "performance" as Performance

GridLayout {
    id: root
    property var metrics: null
    property var motion
    columns: width < Wysun.Appearance.spaceXl * 24 ? 1 : 2
    rowSpacing: Wysun.Appearance.spaceM
    columnSpacing: Wysun.Appearance.spaceM

    Performance.HeroCard {
        Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop
        motion: root.motion; glyph: "memory"; label: "Procesador"; subLabel: "Uso de CPU"
        usage: root.metrics ? root.metrics.cpu : null
        temperature: root.metrics ? root.metrics.cpuTemperature : null
        showTemperature: true
    }
    Performance.HeroCard {
        Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop
        motion: root.motion; glyph: "developer_board"; label: "Memoria"; subLabel: "RAM en uso"
        usage: root.metrics ? root.metrics.memory : null
    }
    Performance.HeroCard {
        Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop
        motion: root.motion; glyph: "hard_drive"; label: "Almacenamiento"; subLabel: "Sistema de archivos /"
        usage: root.metrics ? root.metrics.storage : null
    }
    Performance.HeroCard {
        Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop
        motion: root.motion; glyph: "monitoring"; label: "Gráficos"; subLabel: "Proveedor de GPU"
        usage: root.metrics ? root.metrics.gpu : null
        temperature: root.metrics ? root.metrics.gpuTemperature : null
        showTemperature: true
    }
}
