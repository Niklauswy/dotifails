// Wysun Lock · minimal PAM client. The password lives only in a QML string handed to PamContext:
// it is never logged, never put in argv or the environment and never written to disk.
// The service (assets/pam.d/wysun-lock) delegates to the system's /etc/pam.d/login, like swaylock.
import QtQuick
import Quickshell
import Quickshell.Services.Pam

Scope {
    id: root

    required property bool secure
    required property string configDirectory
    // locked | authenticating | success | failed | maxtries | error
    property string state: "locked"
    property string detail: ""
    property int attempts: 0
    property string pending: ""

    signal authenticated()

    function submit(password: string): bool {
        if (!root.secure || root.state === "authenticating" || root.state === "success" || root.state === "maxtries")
            return false;
        if (password.length === 0)
            return false;
        root.pending = password;
        root.state = "authenticating";
        root.detail = "";
        root.attempts++;
        if (!pam.start()) {
            root.pending = "";
            root.state = "error";
            root.detail = "AUTHENTICATION SERVICE UNAVAILABLE";
            return false;
        }
        return true;
    }

    function abort(): void {
        root.pending = "";
        if (pam.active)
            pam.abort();
    }

    onSecureChanged: {
        if (!root.secure)
            root.abort();
        root.state = "locked";
    }

    PamContext {
        id: pam

        config: "wysun-lock"
        configDirectory: root.configDirectory

        onResponseRequiredChanged: {
            if (!responseRequired)
                return;
            if (root.pending.length === 0) {
                // Only the password conversation is expected; refuse anything else.
                pam.abort();
                root.state = "error";
                return;
            }
            const password = root.pending;
            root.pending = "";
            respond(password);
        }

        onCompleted: result => {
            root.pending = "";
            if (result === PamResult.Success) {
                root.state = "success";
                root.authenticated();
            } else if (result === PamResult.MaxTries) {
                root.state = "maxtries";
                root.detail = "TOO MANY ATTEMPTS";
            } else if (result === PamResult.Failed) {
                root.state = "failed";
            } else {
                root.state = "error";
                root.detail = "AUTHENTICATION ERROR";
            }
        }

        onError: error => {
            root.pending = "";
            root.state = "error";
            root.detail = error === PamError.StartFailed ? "AUTHENTICATION SERVICE UNAVAILABLE" : "AUTHENTICATION ERROR";
        }
    }
}
