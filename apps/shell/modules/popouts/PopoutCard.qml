// Derivado de caelestia-dots/shell/modules/drawers/ContentWindow.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components

Components.StyledRect {
    id: root
    required property var controller
    required property var motion
    property string monitorName: ""
    property real contentOpacity: 1

    radius: Wysun.Appearance.radiusL
    color: Wysun.Appearance.materialMid
    border.width: Wysun.Appearance.borderWidth
    border.color: Wysun.Appearance.materialEdge

    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.spaceXl
        opacity: root.contentOpacity
        spacing: Wysun.Appearance.spaceM

        RowLayout {
            Layout.fillWidth: true
            Components.StyledText {
                Layout.fillWidth: true
                text: "Popout de prueba"
                color: Wysun.Appearance.textStrong
                font.pixelSize: Wysun.Appearance.fontTitle
                font.weight: Font.DemiBold
                Accessible.role: Accessible.Heading
            }
            Components.StyledText {
                text: root.monitorName
                color: Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontSmall
            }
        }

        Components.StyledText {
            Layout.fillWidth: true
            text: "La shell nueva de Wysun está activa. Este panel comprueba el morph, el foco y el cierre sin cargar todavía el dashboard."
            color: Wysun.Appearance.text
            font.pixelSize: Wysun.Appearance.fontBody
            wrapMode: Text.WordWrap
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            Components.StyledText {
                Layout.fillWidth: true
                text: "Escape o clic fuera para cerrar"
                color: Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontSmall
            }
            Components.ActionButton {
                motion: root.motion
                glyph: "close"
                label: "Cerrar"
                onClicked: root.controller.close()
            }
        }
    }
}
