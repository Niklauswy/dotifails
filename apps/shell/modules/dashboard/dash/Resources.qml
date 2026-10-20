// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/dash/Resources.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../../" as Wysun
import "../../../components" as Components
import "../performance" as Performance
import "../" as Dashboard
import "../Logic.js" as Logic

Dashboard.Card {
    id: root
    property var metrics: null
    property var motion
    implicitHeight: row.implicitHeight + padding * 2
    Accessible.role: Accessible.Grouping
    Accessible.name: "Recursos del sistema"

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: root.padding
        spacing: Wysun.Appearance.spaceM
        Repeater {
            model: [
                { label: "CPU", glyph: "memory", value: root.metrics ? root.metrics.cpu : null },
                { label: "Memoria", glyph: "developer_board", value: root.metrics ? root.metrics.memory : null },
                { label: "Disco /", glyph: "hard_drive", value: root.metrics ? root.metrics.storage : null }
            ]
            delegate: ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                spacing: Wysun.Appearance.spaceXs
                Performance.Gauge {
                    Layout.alignment: Qt.AlignHCenter
                    implicitWidth: Wysun.Appearance.spaceXl * 3
                    thickness: Wysun.Appearance.spaceXs + Wysun.Appearance.borderWidth
                    motion: root.motion
                    value: modelData.value
                    label: modelData.label
                }
                Components.StyledText {
                    Layout.alignment: Qt.AlignHCenter
                    text: modelData.label
                    font.pixelSize: Wysun.Appearance.fontSmall
                    color: Wysun.Appearance.muted
                }
            }
        }
    }
}
