// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/utilities/Content.qml (commit 507d66285e9d9fde9330adc64159cfdebb28c19a).
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
    ScrollBar.vertical.policy: ScrollBar.AsNeeded

    ColumnLayout {
        width: root.availableWidth
        spacing: Wysun.Appearance.spaceM

        Toggles {
            Layout.fillWidth: true
            hub: root.hub
            motion: root.motion
            preview: root.preview
        }
        AudioPopout {
            Layout.fillWidth: true
            motion: root.motion
            previewData: root.preview ? ({ volume: 0.42, muted: false, sourceVolume: 0.65, sourceMuted: false, brightness: 0.58 }) : null
        }
        Battery {
            Layout.fillWidth: true
            hub: root.hub
            motion: root.motion
        }
        Network {
            Layout.fillWidth: true
            hub: root.hub
            motion: root.motion
            controller: root.controller
            preview: root.preview
        }
        Bluetooth {
            Layout.fillWidth: true
            hub: root.hub
            motion: root.motion
            preview: root.preview
        }
        SectionCard {
            Layout.fillWidth: true
            motion: root.motion
            title: "Energía y captura"
            IdleInhibit {
                Layout.fillWidth: true
                motion: root.motion
                preview: root.preview
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Wysun.Appearance.borderWidth
                color: Wysun.Appearance.line
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: Wysun.Appearance.spaceS
                ControlButton {
                    Layout.fillWidth: true
                    motion: root.motion
                    label: "Sesión"
                    description: "Bloquear, suspender, reiniciar o apagar"
                    enabled: !root.preview
                    onClicked: root.controller.show("session")
                }
                ControlButton {
                    Layout.fillWidth: true
                    motion: root.motion
                    label: "Wysun Recorder"
                    description: "Abre Wysun Recorder; sus portales y consentimiento no cambian"
                    enabled: !root.preview
                    onClicked: root.controller.launch("recorder")
                }
            }
        }
        Components.StyledText {
            Layout.fillWidth: true
            text: "Wi-Fi, Bluetooth y batería se consultan solo al abrir este panel."
            color: Wysun.Appearance.disabled
            font.pixelSize: Wysun.Appearance.fontCaption
            wrapMode: Text.WordWrap
            motion: root.motion
        }
    }
}
