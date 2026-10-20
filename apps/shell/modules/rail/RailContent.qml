import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Services.SystemTray
import "../../" as Wysun
import "../../components" as Components

Item {
    id: root
    required property var controller
    required property var clock
    required property var motion
    property string screenName: ""
    property string activeTitle: ""
    property var workspaces: []
    property bool trayOwner: false
    property var trayItems: []
    property var trayWindow: null
    property var sink: null
    property int volumePercent: -1
    property bool hasBattery: false
    property real batteryPercentage: 0
    implicitWidth: Wysun.Appearance.railWidth

    Components.StyledRect {
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.spaceXs
        motion: root.motion
        radius: Wysun.Appearance.radiusL
        color: Wysun.Appearance.surface
        border.width: Wysun.Appearance.borderWidth
        border.color: Wysun.Appearance.line
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: Wysun.Appearance.spaceS
        anchors.bottomMargin: Wysun.Appearance.spaceS
        anchors.leftMargin: Wysun.Appearance.spaceS
        anchors.rightMargin: Wysun.Appearance.spaceS
        spacing: Wysun.Appearance.spaceXs

        Components.ActionButton {
            id: brandButton
            motion: root.motion
            compact: true
            glyph: "dashboard"
            label: "Wysun · abrir popout de prueba"
            Layout.alignment: Qt.AlignHCenter
            onClicked: root.controller.toggle("test", root.screenName, root.width / 2,
                brandButton.mapToItem(root, brandButton.width / 2, brandButton.height / 2).y, brandButton)
        }

        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: Wysun.Appearance.borderWidth; color: Wysun.Appearance.line }

        WorkspaceStrip {
            Layout.alignment: Qt.AlignHCenter
            Layout.fillHeight: true
            workspaces: root.workspaces
            motion: root.motion
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(220, Math.max(120, root.height * 0.24))
            visible: root.activeTitle.length > 0
            Components.StyledText {
                anchors.centerIn: parent
                width: Math.max(100, parent.height - Wysun.Appearance.spaceM)
                height: Wysun.Appearance.fontBody + Wysun.Appearance.spaceXs
                rotation: 270
                transformOrigin: Item.Center
                text: root.activeTitle
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                color: Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontSmall
                motion: root.motion
            }
        }

        Components.StyledText {
            Layout.alignment: Qt.AlignHCenter
            text: Qt.formatTime(root.clock.date, "HH") + "\n" + Qt.formatTime(root.clock.date, "mm")
            horizontalAlignment: Text.AlignHCenter
            color: Wysun.Appearance.text
            font.pixelSize: Wysun.Appearance.fontBody
            font.weight: Font.DemiBold
            lineHeight: 0.9
            motion: root.motion
            Accessible.name: "Hora " + Qt.formatTime(root.clock.date, "HH:mm")
        }

        ColumnLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: Wysun.Appearance.spaceXs
            Repeater {
                model: root.trayOwner ? root.trayItems : null
                delegate: Button {
                    required property var modelData
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: 42
                    Layout.preferredHeight: 36
                    padding: 4
                    Accessible.name: modelData.tooltipTitle || modelData.title || "Icono de bandeja"
                    Accessible.role: Accessible.Button
                    onClicked: {
                        if (modelData.onlyMenu && root.trayWindow) modelData.display(root.trayWindow, 0, 0);
                        else if (!modelData.onlyMenu) modelData.activate();
                    }
                    background: Components.StyledRect {
                        motion: root.motion
                        radius: Wysun.Appearance.radiusControl
                        color: parent.hovered ? Wysun.Appearance.hover : "transparent"
                    }
                    contentItem: Image { source: parent.modelData.icon; fillMode: Image.PreserveAspectFit }
                    TapHandler {
                        acceptedButtons: Qt.RightButton
                        onTapped: if (root.trayWindow) modelData.display(root.trayWindow, 0, 0)
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: Wysun.Appearance.borderWidth; color: Wysun.Appearance.line }

        Components.ActionButton {
            motion: root.motion
            compact: true
            glyph: root.sink?.audio?.muted ? "volume_off" : (root.volumePercent < 0 ? "volume_mute" : "volume_up")
            label: root.volumePercent < 0 ? "Audio no disponible" : "Volumen " + root.volumePercent + "%"
            Layout.alignment: Qt.AlignHCenter
            onClicked: root.controller.launch("audio")
        }
        Components.ActionButton {
            motion: root.motion
            compact: true
            glyph: "wifi"
            label: "Conexiones"
            Layout.alignment: Qt.AlignHCenter
            onClicked: root.controller.launch("connections")
        }
        Components.ActionButton {
            visible: root.hasBattery
            motion: root.motion
            compact: true
            glyph: root.batteryPercentage < 0.15 ? "battery_alert" : "battery_full"
            label: "Batería " + Math.round(root.batteryPercentage * 100) + "%"
            Layout.alignment: Qt.AlignHCenter
            onClicked: root.controller.launch("power")
        }
        Components.ActionButton {
            motion: root.motion
            compact: true
            glyph: "power_settings_new"
            label: "Energía y sesión"
            Layout.alignment: Qt.AlignHCenter
            onClicked: root.controller.launch("power")
        }
    }
}
