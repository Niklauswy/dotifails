// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Dash.qml; modules/dashboard/dash/DateTime.qml; Calendar.qml; Media.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "dash" as DashCards

GridLayout {
    id: root
    property var metrics: null
    property var media: null
    property var controller: null
    property var motion
    property string monitorName: ""
    property date now: new Date()
    columns: width < Wysun.Appearance.spaceXl * 24 ? 1 : 2
    rowSpacing: Wysun.Appearance.spaceM
    columnSpacing: Wysun.Appearance.spaceM
    Timer { interval: 60000; running: root.visible; repeat: true; onTriggered: root.now = new Date() }
    Components.StyledRect {
        Layout.fillWidth: true
        implicitHeight: dateLayout.implicitHeight + Wysun.Appearance.spaceXl * 2
        radius: Wysun.Appearance.radiusL
        color: Wysun.Appearance.selection
        ColumnLayout {
            id: dateLayout
            anchors.fill: parent
            anchors.margins: Wysun.Appearance.spaceXl
            spacing: Wysun.Appearance.spaceM
            Components.StyledText { text: Qt.formatTime(root.now, "HH:mm"); color: Wysun.Appearance.selectionText; font.pixelSize: Wysun.Appearance.fontTitle * 2 }
            Components.StyledText { Layout.fillWidth: true; text: Qt.locale("es_MX").toString(root.now, "dddd d 'de' MMMM"); color: Wysun.Appearance.selectionText; font.pixelSize: Wysun.Appearance.fontBody; wrapMode: Text.WordWrap }
            Components.StyledText { Layout.fillWidth: true; text: root.monitorName || "Wysun"; color: Wysun.Appearance.selectionText; font.pixelSize: Wysun.Appearance.fontSmall; elide: Text.ElideRight }
        }
    }
    Components.StyledRect {
        Layout.fillWidth: true
        Layout.fillHeight: true
        implicitHeight: mediaLayout.implicitHeight + Wysun.Appearance.spaceL * 2
        radius: Wysun.Appearance.radiusL
        color: Wysun.Appearance.surfaceRaised
        ColumnLayout {
            id: mediaLayout
            anchors.fill: parent
            anchors.margins: Wysun.Appearance.spaceL
            spacing: Wysun.Appearance.spaceM
            Components.StyledText { text: "Ahora suena"; font.pixelSize: Wysun.Appearance.fontSmall; color: Wysun.Appearance.muted }
            Components.StyledText { Layout.fillWidth: true; text: root.media?.title || "Sin reproducción"; font.pixelSize: Wysun.Appearance.fontHeading; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
            Components.StyledText { Layout.fillWidth: true; text: root.media?.artist || "Tu música, a un clic"; font.pixelSize: Wysun.Appearance.fontBody; color: Wysun.Appearance.muted; elide: Text.ElideRight }
            Components.ActionButton { Layout.fillWidth: true; glyph: "dashboard"; label: "Abrir Wysun Music"; motion: root.motion; enabled: !!root.controller; onClicked: root.controller.launch("music") }
        }
    }
    DashCards.Resources { Layout.columnSpan: root.columns; Layout.fillWidth: true; metrics: root.metrics; motion: root.motion }
    RowLayout {
        Layout.columnSpan: root.columns
        Layout.fillWidth: true
        Components.ActionButton { Layout.fillWidth: true; implicitWidth: 0; glyph: ""; label: "Archivos"; motion: root.motion; enabled: !!root.controller; onClicked: root.controller.launch("files") }
        Components.ActionButton { Layout.fillWidth: true; implicitWidth: 0; glyph: ""; label: "Ajustes"; motion: root.motion; enabled: !!root.controller; onClicked: root.controller.launch("settings") }
    }
}
