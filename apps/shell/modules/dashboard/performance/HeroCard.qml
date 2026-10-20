// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/performance/HeroCard.qml; MemoryCard.qml; StorageCard.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../../" as Wysun
import "../../../components" as Components
import "../Logic.js" as Logic

Components.StyledRect {
    id: root
    required property string label
    property var motion
    property string subLabel: ""
    property var usage: null
    property var temperature: null
    property bool showTemperature: false
    property color accent: Wysun.Appearance.accent
    implicitWidth: Wysun.Appearance.spaceXl * 10
    implicitHeight: layout.implicitHeight + Wysun.Appearance.spaceL * 2
    radius: Wysun.Appearance.radiusL
    color: Wysun.Appearance.surfaceRaised
    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.spaceL
        spacing: Wysun.Appearance.spaceS
        Components.StyledText { text: root.label; font.pixelSize: Wysun.Appearance.fontHeading; color: root.accent }
        Components.StyledText { Layout.fillWidth: true; visible: text !== ""; text: root.subLabel; font.pixelSize: Wysun.Appearance.fontSmall; color: Wysun.Appearance.muted; elide: Text.ElideRight }
        Gauge { Layout.alignment: Qt.AlignHCenter; motion: root.motion; label: root.label; value: root.usage; accent: root.accent }
        Components.StyledText { Layout.alignment: Qt.AlignHCenter; text: Logic.percentText(root.usage); color: Wysun.Appearance.muted; font.pixelSize: Wysun.Appearance.fontSmall }
        Components.StyledText { visible: root.showTemperature; Layout.alignment: Qt.AlignHCenter; text: typeof root.temperature === "number" && isFinite(root.temperature) ? Math.round(root.temperature) + " °C" : "Temperatura: no disponible"; color: Wysun.Appearance.muted; font.pixelSize: Wysun.Appearance.fontSmall }
    }
}
