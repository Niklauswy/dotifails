// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/notifications/Notification.qml (commit 507d66285e9d9fde9330adc64159cfdebb28c19a).
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// Dunst owns the notification lifecycle and the original actions. This card
// only presents the inert history entry and offers copy/remove.
import QtQuick
import QtQuick.Layouts
import Quickshell
import "../../" as Wysun
import "../../components" as Components
import "../../services" as Services
import "../quicksettings" as Quick

Components.StyledRect {
    id: root

    required property var entry
    required property var motion
    required property bool expanded
    signal toggled()
    signal copied()
    signal removed()

    property bool preview: false
    implicitHeight: layout.implicitHeight + Wysun.Appearance.spaceL * 2
    radius: Wysun.Appearance.radiusL
    color: Wysun.Appearance.surfaceRaised
    border.width: Wysun.Appearance.borderWidth
    border.color: notif.critical ? Wysun.Appearance.danger : Wysun.Appearance.line
    Accessible.name: notif.appName + ": " + notif.summary

    Services.NotifData { id: notif; entry: root.entry }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        onClicked: root.toggled()
    }

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.topMargin: Wysun.Appearance.spaceM
        anchors.bottomMargin: Wysun.Appearance.spaceM
        anchors.leftMargin: Wysun.Appearance.spaceXs
        width: Wysun.Appearance.spaceXs
        radius: width / 2
        color: notif.critical ? Wysun.Appearance.danger : Wysun.Appearance.accent
    }

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.spaceL
        anchors.leftMargin: Wysun.Appearance.spaceL + Wysun.Appearance.spaceXs
        spacing: Wysun.Appearance.spaceXs

        RowLayout {
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceS
            Components.MaterialIcon {
                name: notif.glyph
                size: Wysun.Appearance.fontHeading
                color: notif.critical ? Wysun.Appearance.danger : Wysun.Appearance.accent
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Components.StyledText {
                    Layout.fillWidth: true
                    text: notif.appName
                    color: Wysun.Appearance.muted
                    font.pixelSize: Wysun.Appearance.fontSmall
                    elide: Text.ElideRight
                    motion: root.motion
                }
                Components.StyledText {
                    Layout.fillWidth: true
                    text: notif.summary
                    color: Wysun.Appearance.textStrong
                    font.pixelSize: Wysun.Appearance.fontBody
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    maximumLineCount: 2
                    wrapMode: Text.WordWrap
                    motion: root.motion
                }
            }
            Components.StyledRect {
                implicitWidth: urgency.implicitWidth + Wysun.Appearance.spaceM * 2
                implicitHeight: urgency.implicitHeight + Wysun.Appearance.spaceXs * 2
                radius: Wysun.Appearance.radiusS
                color: notif.critical ? Wysun.Appearance.danger : Wysun.Appearance.well
                Components.StyledText {
                    id: urgency
                    anchors.centerIn: parent
                    text: notif.urgencyLabel
                    color: notif.critical ? Wysun.Appearance.canvas : Wysun.Appearance.muted
                    font.pixelSize: Wysun.Appearance.fontCaption
                    motion: root.motion
                }
            }
        }

        Components.StyledText {
            Layout.fillWidth: true
            visible: notif.hasBody
            text: notif.body
            textFormat: Text.PlainText
            color: Wysun.Appearance.text
            font.pixelSize: Wysun.Appearance.fontSmall
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            maximumLineCount: root.expanded ? 40 : 2
            elide: Text.ElideRight
            motion: root.motion
        }

        RowLayout {
            Layout.fillWidth: true
            visible: root.expanded
            spacing: Wysun.Appearance.spaceS
            Components.StyledText {
                Layout.fillWidth: true
                text: "Dunst conserva las acciones originales de la aplicación."
                color: Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontCaption
                wrapMode: Text.WordWrap
                motion: root.motion
            }
            Quick.ControlButton {
                motion: root.motion
                glyph: "content_copy"
                label: "Copiar"
                description: "Copia el cuerpo del aviso"
                onClicked: root.copied()
            }
            Quick.ControlButton {
                motion: root.motion
                glyph: "delete"
                label: "Quitar"
                description: "Quita este aviso del historial de Dunst"
                enabled: !root.preview
                onClicked: root.removed()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceS
            Components.StyledText {
                Layout.fillWidth: true
                text: root.expanded ? "Menos" : "Más"
                color: Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontCaption
                motion: root.motion
            }
            Quick.ControlButton {
                objectName: "notifExpand"
                motion: root.motion
                label: root.expanded ? "Contraer" : "Expandir"
                selected: root.expanded
                onClicked: root.toggled()
            }
        }
    }
}
