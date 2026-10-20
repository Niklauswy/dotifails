// Adaptado de caelestia-dots/shell/modules/utilities/cards/IdleInhibit.qml
// (GPL-3.0), modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "../../" as Wysun
import "../../components" as Components

RowLayout {
    id: root

    required property var motion
    property bool preview: false
    property bool active: false

    spacing: Wysun.Appearance.spaceM

    IdleInhibitor {
        enabled: root.active && !root.preview && root.visible
        window: root.QsWindow.window
    }

    Components.StyledText {
        Layout.fillWidth: true
        text: "Mantener despierto mientras este panel esté abierto"
        font.pixelSize: Wysun.Appearance.fontSmall
        color: Wysun.Appearance.muted
        wrapMode: Text.WordWrap
        motion: root.motion
    }
    ControlButton {
        objectName: "idleInhibitToggle"
        motion: root.motion
        label: root.active ? "Activado" : "Activar"
        selected: root.active
        description: "Se libera automáticamente al cerrar el panel; depende del soporte del compositor"
        enabled: !root.preview
        onClicked: root.active = !root.active
    }
}
