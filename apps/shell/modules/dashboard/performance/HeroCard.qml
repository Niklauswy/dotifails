// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/performance/HeroCard.qml; MemoryCard.qml; StorageCard.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../../" as Wysun
import "../../../components" as Components
import "../" as Dashboard
import "../Logic.js" as Logic

// Gauge plus the reading as text. The temperature line only exists for
// providers that can have one, and says so when the sensor is absent.
Dashboard.Card {
    id: root
    required property string label
    property var motion
    property string glyph: "speed"
    property string subLabel: ""
    property var usage: null
    property var temperature: null
    property bool showTemperature: false

    implicitWidth: Wysun.Appearance.spaceXl * 10
    implicitHeight: layout.implicitHeight + padding * 2
    Accessible.role: Accessible.Grouping
    Accessible.name: label + ": " + Logic.percentText(usage)

    RowLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: root.padding
        spacing: Wysun.Appearance.spaceL

        Gauge {
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: Wysun.Appearance.spaceXl * 4
            motion: root.motion
            label: root.label
            value: root.usage
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: Wysun.Appearance.spaceXs
            RowLayout {
                Layout.fillWidth: true
                spacing: Wysun.Appearance.spaceS
                Components.MaterialIcon { name: root.glyph; size: Wysun.Appearance.fontHeading; color: Wysun.Appearance.accent }
                Components.StyledText {
                    Layout.fillWidth: true
                    text: root.label
                    font.pixelSize: Wysun.Appearance.fontHeading
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                    motion: root.motion
                }
            }
            Components.StyledText {
                Layout.fillWidth: true
                visible: text !== ""
                text: root.subLabel
                font.pixelSize: Wysun.Appearance.fontSmall
                color: Wysun.Appearance.muted
                elide: Text.ElideRight
            }
            Components.StyledText {
                Layout.fillWidth: true
                visible: Logic.percentage(root.usage) === null
                text: Logic.percentText(root.usage)
                color: Wysun.Appearance.text
                font.pixelSize: Wysun.Appearance.fontBody
                elide: Text.ElideRight
            }
            Components.StyledText {
                Layout.fillWidth: true
                visible: root.showTemperature
                text: Logic.temperatureText(root.temperature)
                color: Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontSmall
                elide: Text.ElideRight
            }
        }
    }
}
