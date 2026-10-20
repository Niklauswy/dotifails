// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/dash/DateTime.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../../" as Wysun
import "../../../components" as Components
import "../" as Dashboard
import "../Logic.js" as Logic

// Clock card in the primary container role: the one place of the dashboard that
// carries the Material You accent, as in the upstream DateTime.
Dashboard.Card {
    id: root
    property date now: new Date()
    property string monitorName: ""
    property var motion
    color: Wysun.Appearance.selection
    implicitHeight: layout.implicitHeight + padding * 2
    Accessible.role: Accessible.StaticText
    Accessible.name: Logic.clockText(now) + ", " + Logic.dateText(now)

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: root.padding
        spacing: Wysun.Appearance.spaceS
        Item { Layout.fillHeight: true }
        Components.StyledText {
            Layout.fillWidth: true
            text: Logic.clockText(root.now)
            color: Wysun.Appearance.selectionText
            font.pixelSize: Wysun.Appearance.fontTitle * 2.5
            font.weight: Font.DemiBold
            motion: root.motion
        }
        Components.StyledText {
            Layout.fillWidth: true
            text: Logic.dateText(root.now)
            color: Wysun.Appearance.selectionText
            font.pixelSize: Wysun.Appearance.fontHeading
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
            motion: root.motion
        }
        Components.StyledText {
            Layout.fillWidth: true
            visible: text !== ""
            text: root.monitorName ? "Pantalla " + root.monitorName : ""
            color: Wysun.Appearance.selectionText
            opacity: 0.75
            font.pixelSize: Wysun.Appearance.fontSmall
            elide: Text.ElideRight
        }
        Item { Layout.fillHeight: true }
    }
}
