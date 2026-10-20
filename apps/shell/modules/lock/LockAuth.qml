// Cliente PAM mínimo de Wysun para la pantalla de bloqueo QML opt-in.
// Derivado conceptualmente de la jerarquía de estados de
// caelestia-dots/shell modules/lock/center/{InputField,StateMessage}.qml,
// commit 507d66285e9d9fde9330adc64159cfdebb28c19a (GPL-3.0). No se copia
// modules/lock/Pam.qml ni su IPC. Véanse THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
// La contraseña vive solo en una cadena QML y se entrega a PamContext; nunca
// se registra, no toca argv/entorno ni se escribe en disco.
import QtQuick
import Quickshell
import Quickshell.Services.Pam
import "LockPolicy.js" as Policy

Scope {
    id: root

    required property bool secure
    required property string configDirectory
    property string state: "locked"
    property string detail: ""
    property int attempts: 0
    property string pending: ""

    signal authenticated()

    function reset() {
        pending = "";
        state = "locked";
        detail = "";
        attempts = 0;
    }

    function submit(password) {
        if (!root.secure || root.state === "authenticating" || state === "success")
            return false;
        if (typeof password !== "string" || password.length === 0)
            return false;
        root.pending = password;
        root.state = "authenticating";
        root.detail = "";
        root.attempts++;
        if (!pam.start()) {
            root.pending = "";
            root.state = "error";
            root.detail = "";
            return false;
        }
        return true;
    }

    function abort() {
        root.pending = "";
        if (pam.active) pam.abort();
    }

    onSecureChanged: {
        if (root.secure) {
            root.reset();
        } else {
            root.abort();
            root.state = "locked";
        }
    }

    PamContext {
        id: pam

        config: "wysun-lock"
        configDirectory: root.configDirectory

        onResponseRequiredChanged: {
            if (!responseRequired) return;
            if (root.pending.length === 0) {
                // Only the password conversation is expected. Refuse any other
                // prompt instead of leaving an answer pending indefinitely.
                pam.abort();
                root.state = "error";
                return;
            }
            var password = root.pending;
            root.pending = "";
            respond(password);
        }

        onCompleted: function(result) {
            root.pending = "";
            if (result === PamResult.Success) {
                root.state = "success";
                root.authenticated();
                return;
            }
            if (result === PamResult.MaxTries) {
                root.state = "maxtries";
                return;
            }
            if (result === PamResult.Failed) {
                root.state = "failed";
                return;
            }
            root.state = "error";
        }

        onError: function(error) {
            root.pending = "";
            root.state = "error";
            root.detail = error === PamError.StartFailed ? "PAM no está disponible"
                        : error === PamError.TryAuthFailed ? "el servicio rechazó el intento"
                        : "error interno del servicio";
        }
    }
}
