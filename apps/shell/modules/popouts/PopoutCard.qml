// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/drawers/Panels.qml; modules/dashboard/Wrapper.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "../dashboard" as Dashboard

Components.StyledRect {
    id: root
    required property var controller
    required property var motion
    property string monitorName: ""
    property real contentOpacity: 1
    property bool live: true
    property bool sampling: visible
    property var providers: null
    property alias dashboardTab: dashboard.currentIndex
    radius: Wysun.Appearance.radiusL
    color: Wysun.Appearance.materialMid
    border.width: Wysun.Appearance.borderWidth
    border.color: Wysun.Appearance.materialEdge
    clip: true
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.spaceL
        opacity: root.contentOpacity
        spacing: Wysun.Appearance.spaceM
        RowLayout {
            Layout.fillWidth: true
            Components.StyledText { Layout.fillWidth: true; text: "Wysun"; color: Wysun.Appearance.textStrong; font.pixelSize: Wysun.Appearance.fontTitle; font.weight: Font.DemiBold; Accessible.role: Accessible.Heading }
            Components.StyledText { Layout.maximumWidth: root.width / 3; text: root.monitorName; color: Wysun.Appearance.muted; font.pixelSize: Wysun.Appearance.fontSmall; elide: Text.ElideRight }
            Components.ActionButton { objectName: "closePopout"; motion: root.motion; compact: true; glyph: "close"; label: "Cerrar panel"; onClicked: root.controller.close() }
        }
        // The integrator may add loaders here for the other surface modules.
        // All those loaders must share this single focused host/controller.
        Dashboard.Wrapper {
            id: dashboard
            Layout.fillWidth: true
            Layout.fillHeight: true
            controller: root.controller
            motion: root.motion
            monitorName: root.monitorName
            live: root.live
            sampling: root.sampling
            fixtureProviders: root.providers
            
        }
    }
}
