// Superficie de bloqueo por salida de Wysun. La sesión la protege
// WlSessionLock (ext-session-lock-v1 de Quickshell 0.3); esta superficie solo
// pinta la presentación y delega la autenticación en LockAuth.
// Derivado de modules/lock/Center.qml y center/Clock.qml de
// caelestia-dots/shell, commit 507d66285e9d9fde9330adc64159cfdebb28c19a
// (GPL-3.0), modificado para Wysun. Véanse THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
// No se copia LockSurface.qml ni se captura pantalla, cava o visualizador.
import QtQuick
import Quickshell.Wayland
import "../../" as Wysun

WlSessionLockSurface {
    id: root

    required property WlSessionLock sessionLock
    required property var auth
    property bool mediaEnabled: false
    property var motion: null

    color: Wysun.Appearance.canvas

    LockPanel {
        anchors.fill: parent
        secure: root.sessionLock.secure
        authenticating: root.auth ? root.auth.state === "authenticating" : false
        state: root.auth ? root.auth.state : "locked"
        detail: root.auth ? root.auth.detail : ""
        attempts: root.auth ? root.auth.attempts : 0
        mediaEnabled: root.mediaEnabled
        motion: root.motion
        onSubmitted: function(password) { if (root.auth) root.auth.submit(password); }
    }
}
