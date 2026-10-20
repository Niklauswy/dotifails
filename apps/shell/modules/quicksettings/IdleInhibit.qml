// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/utilities/cards/IdleInhibit.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
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
    spacing: Wysun.Appearance.spaceM
    IdleInhibitor {
        enabled: awake.selected && !root.preview && root.visible
        window: root.QsWindow.window
    }
    Components.StyledText {
        Layout.fillWidth: true
        text: "Mantener despierto mientras este panel esté abierto"
        font.pixelSize: Wysun.Appearance.fontSmall
        color: Wysun.Appearance.muted
        wrapMode: Text.WordWrap
    }
    ControlButton {
        id: awake
        objectName: "idleInhibitToggle"
        motion: root.motion
        label: selected ? "Activado" : "Activar"
        onClicked: selected = !selected
        Accessible.description: "Se libera automáticamente al cerrar el panel. Depende del soporte del compositor."
    }
}
