pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Pam

// Password authentication for the session lock. Uses the system "swaylock" PAM
// service (/etc/pam.d/swaylock), the same stack the swaylock fallback uses.
Scope {
    id: root

    enum PamState {
        None,
        Error,
        MaxTries,
        Failed
    }

    required property WlSessionLock lock

    readonly property alias passwd: passwd
    readonly property bool verifying: passwd.active

    property string lockMessage
    property int state
    property string buffer

    signal flashMsg
    signal authenticated

    function handleKey(event: KeyEvent): void {
        if (passwd.active || state === Pam.MaxTries)
            return;

        if (event.key === Qt.Key_Enter || event.key === Qt.Key_Return) {
            if (buffer.length > 0)
                passwd.start();
        } else if (event.key === Qt.Key_Escape) {
            buffer = "";
        } else if (event.key === Qt.Key_Backspace) {
            if (event.modifiers & Qt.ControlModifier)
                buffer = "";
            else
                buffer = buffer.slice(0, -1);
        } else if (/^[^\x00-\x1F\x7F-\x9F]+$/.test(event.text)) {
            // Allow anything except control characters
            buffer += event.text;
        }
    }

    function submit(): void {
        if (!passwd.active && state !== Pam.MaxTries && buffer.length > 0)
            passwd.start();
    }

    PamContext {
        id: passwd

        config: "swaylock"

        onMessageChanged: {
            if (message.startsWith("The account is locked"))
                root.lockMessage = message;
            else if (root.lockMessage && message.endsWith(" left to unlock)"))
                root.lockMessage += "\n" + message;
        }

        onResponseRequiredChanged: {
            if (!responseRequired)
                return;

            respond(root.buffer);
            root.buffer = "";
        }

        onCompleted: res => {
            if (res === PamResult.Success)
                return root.authenticated();

            if (res === PamResult.Error)
                root.state = Pam.Error;
            else if (res === PamResult.MaxTries)
                root.state = Pam.MaxTries;
            else
                root.state = Pam.Failed;

            root.buffer = "";
            root.flashMsg();
            pwdStateReset.restart();
        }
    }

    Timer {
        id: pwdStateReset

        interval: 4000
        onTriggered: {
            if (root.state !== Pam.MaxTries)
                root.state = Pam.None;
        }
    }

    Connections {
        function onSecureChanged(): void {
            if (root.lock.secure) {
                root.buffer = "";
                root.state = Pam.None;
                root.lockMessage = "";
            }
        }

        target: root.lock
    }
}
