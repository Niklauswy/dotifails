// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/session/Content.qml (commit 507d66285e9d9fde9330adc64159cfdebb28c19a).
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// Lock, suspend, log out, restart and power off through bounded providers.
// Irreversible actions need a second, explicit confirmation; nothing runs when
// the panel opens and no timer keeps running behind a closed surface.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "../quicksettings" as Quick
import "../../services" as Services

Item {
    id: root

    required property var controller
    required property var motion
    property bool preview: false
    // Gallery and tests drive the menu with a fixed capability set.
    property var demoSession: ({ available: true, canLock: true, canLogout: true, canSuspend: true, canReboot: true, canPowerOff: true })

    // The action waiting for its confirmation ("" when none).
    property string pending: ""
    readonly property var hub: preview ? fallbackDemo : provider
    readonly property var capabilities: hub.states.session || ({ available: false })
    readonly property bool ready: capabilities.available === true

    readonly property var entries: [
        { action: "session-lock", glyph: "lock", label: "Bloquear", detail: "Bloquea la pantalla con Wysun Lock", can: "canLock", confirm: false },
        { action: "session-suspend", glyph: "bedtime", label: "Suspender", detail: "Bloquea y suspende el equipo", can: "canSuspend", confirm: false },
        { action: "session-logout", glyph: "logout", label: "Cerrar sesión", detail: "Cierra Hyprland y las ventanas abiertas", can: "canLogout", confirm: true },
        { action: "session-reboot", glyph: "restart_alt", label: "Reiniciar", detail: "Reinicia el equipo", can: "canReboot", confirm: true },
        { action: "session-poweroff", glyph: "power_settings_new", label: "Apagar", detail: "Apaga el equipo", can: "canPowerOff", confirm: true }
    ]

    function allowed(entry) { return ready && capabilities[entry.can] === true && !hub.busy; }
    function request(entry) {
        if (!allowed(entry)) return;
        if (entry.confirm && pending !== entry.action) {
            pending = entry.action;
            return;
        }
        pending = "";
        if (!preview) provider.act(entry.action);
    }

    QtObject {
        id: fallbackDemo
        property bool busy: false
        property var states: ({ session: root.demoSession })
        property string error: ""
        function act() { return false; }
        function refresh() { return false; }
    }

    Services.DesktopServices {
        id: provider
        domains: "session"
        active: root.visible && !root.preview
        onActionDone: root.controller.close()
    }

    onVisibleChanged: if (!visible) pending = ""
    // A forgotten confirmation expires by itself; the timer only runs while one is pending.
    Timer {
        interval: 6000
        running: root.pending !== ""
        onTriggered: root.pending = ""
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
                    text: "Sesión"
                    color: Wysun.Appearance.textStrong
                    font.pixelSize: Wysun.Appearance.fontTitle
                    font.weight: Font.DemiBold
                    motion: root.motion
                    Accessible.role: Accessible.Heading
                }
                Components.StyledText {
                    Layout.fillWidth: true
                    text: root.pending !== "" ? "Confirma la acción: no se puede deshacer" : "Escape o un clic fuera cierran este panel"
                    color: root.pending !== "" ? Wysun.Appearance.warning : Wysun.Appearance.muted
                    font.pixelSize: Wysun.Appearance.fontSmall
                    motion: root.motion
                }
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
            implicitHeight: errorText.implicitHeight + Wysun.Appearance.spaceM * 2
            radius: Wysun.Appearance.radiusM
            color: Wysun.Appearance.well
            border.width: Wysun.Appearance.borderWidth
            border.color: Wysun.Appearance.danger
            Components.StyledText {
                id: errorText
                anchors.fill: parent
                anchors.margins: Wysun.Appearance.spaceM
                text: provider.error
                color: Wysun.Appearance.danger
                font.pixelSize: Wysun.Appearance.fontSmall
                wrapMode: Text.WordWrap
                motion: root.motion
            }
        }

        Components.StyledText {
            visible: !root.ready
            Layout.fillWidth: true
            text: "El estado de la sesión no está disponible (" + (root.capabilities.error || "sin datos") + ")."
            color: Wysun.Appearance.muted
            font.pixelSize: Wysun.Appearance.fontSmall
            wrapMode: Text.WordWrap
            motion: root.motion
        }

        Repeater {
            model: root.entries
            Quick.ControlButton {
                id: button
                required property var modelData
                objectName: modelData.action
                Layout.fillWidth: true
                motion: root.motion
                glyph: modelData.glyph
                label: root.pending === modelData.action ? "Confirmar: " + modelData.label : modelData.label
                selected: root.pending === modelData.action
                description: root.allowed(modelData) ? modelData.detail : modelData.label + ": no disponible ahora"
                enabled: root.allowed(modelData)
                onClicked: root.request(modelData)
            }
        }

        Quick.ControlButton {
            visible: root.pending !== ""
            Layout.fillWidth: true
            motion: root.motion
            label: "Cancelar"
            description: "Descarta la confirmación pendiente"
            onClicked: root.pending = ""
        }

        Item { Layout.fillHeight: true }
    }
}
