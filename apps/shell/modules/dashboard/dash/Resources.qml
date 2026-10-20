// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/dash/Resources.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../../" as Wysun
import "../../../components" as Components
import "../performance" as Performance
import "../Logic.js" as Logic

Components.StyledRect {
    id: root
    property var metrics: null
    property var motion
    color: Wysun.Appearance.surfaceRaised
    radius: Wysun.Appearance.radiusL
    implicitHeight: row.implicitHeight + Wysun.Appearance.spaceL * 2
    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.spaceL
        spacing: Wysun.Appearance.spaceM
        Repeater {
            model: [{label:"CPU",value:root.metrics?.cpu}, {label:"Memoria",value:root.metrics?.memory}, {label:"Disco /",value:root.metrics?.storage}]
            delegate: ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                Performance.Gauge { Layout.alignment: Qt.AlignHCenter; implicitWidth: Wysun.Appearance.spaceXl * 3; implicitHeight: implicitWidth; motion: root.motion; value: modelData.value; label: modelData.label }
                Components.StyledText { Layout.alignment: Qt.AlignHCenter; text: modelData.label; font.pixelSize: Wysun.Appearance.fontSmall }
                Components.StyledText { Layout.alignment: Qt.AlignHCenter; text: Logic.percentText(modelData.value); font.pixelSize: Wysun.Appearance.fontSmall; color: Wysun.Appearance.muted }
            }
        }
    }
}
