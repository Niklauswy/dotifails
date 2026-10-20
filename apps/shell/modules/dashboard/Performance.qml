// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Performance.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "performance" as Performance

GridLayout {
    id: root
    property var metrics: null
    property var motion
    columns: width < Wysun.Appearance.spaceXl * 24 ? 1 : 2
    rowSpacing: Wysun.Appearance.spaceM
    columnSpacing: Wysun.Appearance.spaceM
    Performance.HeroCard { Layout.fillWidth: true; motion: root.motion; label: "Procesador"; subLabel: "Uso de CPU"; usage: root.metrics?.cpu; temperature: root.metrics?.cpuTemperature; showTemperature: true }
    Performance.HeroCard { Layout.fillWidth: true; motion: root.motion; label: "Memoria"; subLabel: "RAM en uso"; usage: root.metrics?.memory }
    Performance.HeroCard { Layout.fillWidth: true; motion: root.motion; label: "Almacenamiento"; subLabel: "Sistema de archivos /"; usage: root.metrics?.storage }
    Performance.HeroCard { Layout.fillWidth: true; motion: root.motion; label: "Gráficos"; subLabel: "Proveedor de GPU"; usage: root.metrics?.gpu; temperature: root.metrics?.gpuTemperature; showTemperature: true }
}
