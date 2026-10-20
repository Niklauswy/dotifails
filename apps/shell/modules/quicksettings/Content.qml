// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/utilities/Content.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
ScrollView {
    id: root
    required property var hub
    required property var motion
    required property var controller
    property bool preview: false
    contentWidth: availableWidth
    clip: true
    ColumnLayout {
        width: root.availableWidth
        spacing: Wysun.Appearance.spaceL
        Toggles { Layout.fillWidth: true; hub: root.hub; motion: root.motion }
        AudioPopout { Layout.fillWidth: true; hub: root.hub; motion: root.motion }
        Battery { Layout.fillWidth: true; hub: root.hub }
        IdleInhibit { Layout.fillWidth: true; motion: root.motion; preview: root.preview }
        Network { Layout.fillWidth: true; hub: root.hub; motion: root.motion; controller: root.controller }
        Bluetooth { Layout.fillWidth: true; hub: root.hub; motion: root.motion }
        ControlButton {
            Layout.fillWidth: true
            motion: root.motion
            label: "Abrir Wysun Recorder"
            onClicked: root.controller.launch("recorder")
        }
    }
}
