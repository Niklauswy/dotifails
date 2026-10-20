// Adaptado de caelestia-dots/shell/modules/sidebar/NotifDock.qml,
// modules/notifications/Content.qml y services/NotifData.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// Dunst is the only notification server and keeps its own toasts. This centre
// reads a bounded history snapshot and never registers a second D-Bus owner.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import "../../" as Wysun
import "../../components" as Components
import "../../services" as Services
import "../quicksettings" as Quick

Item {
    id: root

    required property var controller
    required property var motion
    property bool preview: false
    property var demoEntries: []

    property string expandedId: ""
    property bool clearArmed: false
    readonly property var hub: preview ? fallbackDemo : provider

    Services.DesktopServices {
        id: provider
        domains: "notifications"
        active: root.visible && !root.preview
    }
    QtObject {
        id: fallbackDemo
        property bool busy: false
        property var states: ({ notifications: { available: true, paused: false, items: root.demoEntries } })
        function act() { return false; }
    }
    Services.Notifs {
        id: notifs
        hub: root.hub
    }
    readonly property var rows: root.preview ? root.demoEntries : notifs.list

    function toggleExpanded(id) { expandedId = expandedId === id ? "" : id; }
    function copyEntry(entry) { Quickshell.clipboardText = String(entry.body || ""); }
    function removeEntry(entry) {
        if (!root.preview) provider.act("notifications-remove", String(entry.id || ""));
    }
    function armClear() {
        if (clearArmed) {
            clearArmed = false;
            if (!root.preview) provider.act("notifications-clear");
        } else {
            clearArmed = true;
            clearTimer.restart();
        }
    }

    Timer {
        id: clearTimer
        interval: 4000
        onTriggered: root.clearArmed = false
    }
    // Polling exists only while the centre is open. A closed surface runs no timer.
    Timer {
        interval: 4000
        repeat: true
        running: root.visible && !root.preview
        onTriggered: if (!provider.busy) provider.refresh()
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
                    text: "Avisos"
                    color: Wysun.Appearance.textStrong
                    font.pixelSize: Wysun.Appearance.fontTitle
                    font.weight: Font.DemiBold
                    motion: root.motion
                    Accessible.role: Accessible.Heading
                }
                Components.StyledText {
                    Layout.fillWidth: true
                    text: root.rows.length + (root.rows.length === 1 ? " aviso en el historial" : " avisos en el historial")
                    color: Wysun.Appearance.muted
                    font.pixelSize: Wysun.Appearance.fontSmall
                    motion: root.motion
                }
            }
            Quick.ControlButton {
                motion: root.motion
                glyph: notifs.dnd ? "notifications_off" : "do_not_disturb_on"
                label: notifs.dnd ? "Reactivar avisos" : "No molestar"
                selected: notifs.dnd
                description: "Pausa o reanuda los avisos de Dunst"
                enabled: notifs.available && !root.preview && !provider.busy
                onClicked: notifs.toggleDnd()
            }
            Quick.ControlButton {
                motion: root.motion
                label: "Actualizar"
                enabled: !root.preview && !provider.busy
                onClicked: provider.refresh()
            }
            Quick.ControlButton {
                motion: root.motion
                glyph: "close"
                label: "Cerrar"
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
                Quick.ControlButton {
                    motion: root.motion
                    label: "Reintentar"
                    enabled: !provider.busy
                    onClicked: provider.refresh()
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Components.StyledText {
                anchors.centerIn: parent
                width: Math.min(360, parent.width)
                visible: root.rows.length === 0
                horizontalAlignment: Text.AlignHCenter
                text: notifs.available || root.preview
                    ? "No hay avisos en el historial.\nDunst seguirá mostrando sus propios toasts."
                    : notifs.error
                color: Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontSmall
                wrapMode: Text.WordWrap
                motion: root.motion
            }
            ListView {
                id: list
                anchors.fill: parent
                visible: root.rows.length > 0
                clip: true
                spacing: Wysun.Appearance.spaceS
                model: root.rows
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Item {
                    id: delegate
                    required property var modelData
                    width: list.width
                    height: card.implicitHeight + Wysun.Appearance.spaceS
                    NotificationCard {
                        id: card
                        width: parent.width
                        entry: delegate.modelData
                        motion: root.motion
                        expanded: root.expandedId === String(delegate.modelData.id || "")
                        preview: root.preview
                        onToggled: root.toggleExpanded(String(delegate.modelData.id || ""))
                        onCopied: root.copyEntry(delegate.modelData)
                        onRemoved: root.removeEntry(delegate.modelData)
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceS
            Components.StyledText {
                Layout.fillWidth: true
                text: "Dunst conserva los toasts, la caducidad y las acciones originales. Aquí solo se lee su historial."
                color: Wysun.Appearance.disabled
                font.pixelSize: Wysun.Appearance.fontCaption
                wrapMode: Text.WordWrap
                motion: root.motion
            }
            Quick.ControlButton {
                motion: root.motion
                glyph: "delete_sweep"
                label: root.clearArmed ? "Confirmar vaciado" : "Vaciar historial"
                description: "Elimina el historial de Dunst; no cierra los toasts visibles"
                enabled: !root.preview && notifs.available && root.rows.length > 0 && !provider.busy
                onClicked: root.armClear()
            }
        }
    }
}
