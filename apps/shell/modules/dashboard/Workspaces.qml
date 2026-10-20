// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Content.qml (cuarta pestaña sustituida para Wysun), commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components

ColumnLayout {
    id: root
    property var workspaces: []
    property var windows: []
    property var controller: null
    property var motion
    spacing: Wysun.Appearance.spaceM
    Components.StyledText { text: "Tus escritorios"; font.pixelSize: Wysun.Appearance.fontTitle }
    Components.StyledText { Layout.fillWidth: true; text: root.workspaces.length ? "Selecciona un escritorio para continuar." : "No hay escritorios disponibles en esta pantalla."; wrapMode: Text.WordWrap; font.pixelSize: Wysun.Appearance.fontBody; color: Wysun.Appearance.muted }
    Repeater {
        model: root.workspaces
        delegate: Components.StyledRect {
            id: workspaceCard
            required property var modelData
            readonly property var clients: root.windows.filter(w => w.workspace?.id === modelData.id)
            Layout.fillWidth: true
            implicitHeight: workspaceLayout.implicitHeight + Wysun.Appearance.spaceM * 2
            color: modelData.active ? Wysun.Appearance.selection : Wysun.Appearance.surfaceRaised
            radius: Wysun.Appearance.radiusM
            ColumnLayout {
                id: workspaceLayout
                anchors.fill: parent
                anchors.margins: Wysun.Appearance.spaceM
                spacing: Wysun.Appearance.spaceS
                Components.ActionButton { Layout.fillWidth: true; motion: root.motion; glyph: "dashboard"; selected: workspaceCard.modelData.active || false; label: "Escritorio " + workspaceCard.modelData.name + (workspaceCard.modelData.active ? " · actual" : ""); onClicked: { workspaceCard.modelData.activate(); if (root.controller) root.controller.close(); } }
                Repeater {
                    model: workspaceCard.clients
                    delegate: Components.ActionButton { required property var modelData; Layout.fillWidth: true; glyph: ""; label: modelData.title || modelData.appId || "Ventana"; motion: root.motion; enabled: !!root.controller && !!modelData.wayland; onClicked: root.controller.activateWindow(modelData) }
                }
                Components.StyledText { visible: workspaceCard.clients.length === 0; text: "Sin ventanas"; font.pixelSize: Wysun.Appearance.fontSmall; color: Wysun.Appearance.muted }
            }
        }
    }
}
