// Adaptado de caelestia-dots/shell/modules/utilities/Wrapper.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "../../services" as Services

Item {
    id: root

    required property var controller
    required property var motion
    property bool preview: false
    property var demoHub: null

    readonly property var fallbackDemo: QtObject {
        property bool busy: false
        property var states: ({
            network: { available: true, enabled: true, devices: [{ device: "wlan0", type: "wifi", state: "connected", connection: "Casa" }], saved: [{ uuid: "demo", name: "Casa", type: "802-11-wireless" }] },
            bluetooth: { available: true, enabled: true, devices: [{ address: "AA:BB:CC:DD:EE:FF", name: "Auriculares" }] },
            battery: { available: true, percent: 81, status: "Cargando" }
        })
        function act() { return false; }
    }
    readonly property var hub: preview ? (demoHub || fallbackDemo) : provider

    Services.DesktopServices {
        id: provider
        domains: "network,bluetooth,battery"
        active: root.visible && !root.preview
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.spaceL
        spacing: Wysun.Appearance.spaceM

        RowLayout {
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceS
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Components.StyledText {
                    Layout.fillWidth: true
                    text: "Ajustes rápidos"
                    color: Wysun.Appearance.textStrong
                    font.pixelSize: Wysun.Appearance.fontTitle
                    font.weight: Font.DemiBold
                    motion: root.motion
                    Accessible.role: Accessible.Heading
                }
                Components.StyledText {
                    Layout.fillWidth: true
                    text: "Wi-Fi, sonido, pantalla y sesión"
                    color: Wysun.Appearance.muted
                    font.pixelSize: Wysun.Appearance.fontSmall
                    motion: root.motion
                }
            }
            ControlButton {
                motion: root.motion
                glyph: "close"
                label: "Cerrar"
                description: "Cierra el panel; Escape y un clic fuera también lo cierran"
                enabled: !root.preview
                onClicked: root.controller.close()
            }
        }

        Components.StyledRect {
            visible: provider.error.length > 0 && !root.preview
            Layout.fillWidth: true
            implicitHeight: errorRow.implicitHeight + Wysun.Appearance.spaceM * 2
            radius: Wysun.Appearance.radiusM
            color: Wysun.Appearance.well
            border.width: Wysun.Appearance.borderWidth
            border.color: Wysun.Appearance.danger
            RowLayout {
                id: errorRow
                anchors.fill: parent
                anchors.margins: Wysun.Appearance.spaceM
                spacing: Wysun.Appearance.spaceS
                Components.StyledText {
                    Layout.fillWidth: true
                    text: provider.error
                    color: Wysun.Appearance.danger
                    font.pixelSize: Wysun.Appearance.fontSmall
                    wrapMode: Text.WordWrap
                    motion: root.motion
                }
                ControlButton {
                    motion: root.motion
                    label: "Reintentar"
                    enabled: !provider.busy
                    onClicked: provider.refresh()
                }
            }
        }

        Content {
            Layout.fillWidth: true
            Layout.fillHeight: true
            hub: root.hub
            motion: root.motion
            controller: root.controller
            preview: root.preview
        }
    }
}
