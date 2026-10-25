// Wysun greeter: the refinement terminal as the login screen, through greetd.
// Runs with the distribution's Quickshell (no Wysun plugin) inside a minimal Hyprland started by
// greetd as its own user. The password goes straight from the hidden field to greetd; nothing is
// written except the last user and session (no secrets) in the greeter's state file.
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Services.Greetd

Scope {
    id: root

    readonly property string statePath: Quickshell.env("WYSUN_GREETER_STATE") || "/var/lib/wysun-greeter/state.json"
    readonly property string sessionsDir: Quickshell.env("WYSUN_GREETER_SESSIONS") || "/usr/share/wayland-sessions"
    readonly property string passwdPath: Quickshell.env("WYSUN_GREETER_PASSWD") || "/etc/passwd"
    readonly property bool reducedMotion: Quickshell.env("ORBIT_REDUCED_MOTION") === "1"

    property var users: []          // [name]
    property var sessions: []       // [{name, exec}]
    property int userIndex: 0
    property int sessionIndex: 0
    property var saved: ({})
    property string authState: "locked"
    property string message: ""
    property string pending: ""
    property bool leaving: false
    property bool armedPower: false
    property string armedAction: ""

    readonly property string user: users.length ? users[userIndex] : ""
    readonly property var session: sessions.length ? sessions[sessionIndex] : null
    readonly property string hints: (session ? "SESSION  " + session.name.toUpperCase() : "NO SESSIONS FOUND")
        + "   ·   TAB USER   ·   F2 SESSION   ·   F10 RESTART   ·   F12 POWER"

    function parseUsers(text: string): void {
        const found = [];
        for (const line of text.split("\n")) {
            const fields = line.split(":");
            if (fields.length < 7)
                continue;
            const uid = Number(fields[2]);
            const shell = fields[6];
            if (uid >= 1000 && uid < 60000 && !/(nologin|false)$/.test(shell))
                found.push(fields[0]);
        }
        root.users = found;
        root.restore();
    }

    function parseSessions(text: string): void {
        const found = [];
        for (const line of text.split("\n")) {
            const [name, exec] = line.split("\t");
            if (name && exec)
                found.push({ name: name, exec: exec.replace(/\s%[A-Za-z]/g, "").trim() });
        }
        found.sort((a, b) => a.name.localeCompare(b.name));
        root.sessions = found;
        root.restore();
    }

    // Last user, and that user's last session; the Wysun session when there is no history yet.
    function restore(): void {
        const last = root.saved.lastUser;
        const user = root.users.indexOf(last);
        if (user >= 0)
            root.userIndex = user;
        root.pickSession();
    }

    function pickSession(): void {
        const wanted = (root.saved.sessions || {})[root.user];
        let index = root.sessions.findIndex(s => s.name === wanted);
        if (index < 0)
            index = root.sessions.findIndex(s => /wysun/i.test(s.name));
        root.sessionIndex = Math.max(0, index);
    }

    function remember(): void {
        const next = Object.assign({}, root.saved);
        next.lastUser = root.user;
        next.sessions = Object.assign({}, next.sessions || {});
        if (root.session)
            next.sessions[root.user] = root.session.name;
        root.saved = next;
        stateFile.setText(JSON.stringify(next) + "\n");
    }

    function navigate(action: string): void {
        if (root.authState === "authenticating" || root.authState === "success")
            return;
        if (action === "next" || action === "previous") {
            if (root.users.length > 1) {
                root.userIndex = (root.userIndex + (action === "next" ? 1 : root.users.length - 1)) % root.users.length;
                root.pickSession();
            }
        } else if (action === "session") {
            if (root.sessions.length)
                root.sessionIndex = (root.sessionIndex + 1) % root.sessions.length;
        } else if (action === "reboot" || action === "poweroff") {
            // Press twice to confirm; the first press only arms it for a few seconds.
            if (root.armedAction === action) {
                Quickshell.execDetached(["systemctl", action]);
            } else {
                root.armedAction = action;
                root.message = action === "reboot" ? "PRESS F10 AGAIN TO RESTART" : "PRESS F12 AGAIN TO POWER OFF";
                disarm.restart();
            }
        }
    }

    function submit(password: string): void {
        if (!Greetd.available || !root.user || !root.session) {
            root.authState = "error";
            root.message = !Greetd.available ? "GREETD IS NOT AVAILABLE" : "NO USER OR SESSION";
            return;
        }
        root.pending = password;
        root.message = "";
        root.authState = "authenticating";
        Greetd.createSession(root.user);
    }

    Timer {
        id: disarm
        interval: 3000
        onTriggered: {
            root.armedAction = "";
            root.message = "";
        }
    }

    Connections {
        target: Greetd

        function onAuthMessage(message: string, error: bool, responseRequired: bool, echoResponse: bool): void {
            if (responseRequired) {
                if (root.pending.length === 0) {
                    // Only one secret prompt is supported; anything further is refused.
                    Greetd.cancelSession();
                    root.authState = "error";
                    root.message = "UNSUPPORTED AUTHENTICATION STEP";
                    return;
                }
                const password = root.pending;
                root.pending = "";
                Greetd.respond(password);
            } else if (message.length) {
                root.message = message.toUpperCase();
            }
        }

        // Quickshell ends the greetd session itself after an authentication error.
        function onAuthFailure(message: string): void {
            root.pending = "";
            root.authState = "failed";
        }

        function onReadyToLaunch(): void {
            root.pending = "";
            root.authState = "success";
            root.remember();
            granted.restart();
        }

        function onError(error: string): void {
            root.pending = "";
            root.authState = "error";
            root.message = error.toUpperCase();
        }
    }

    // Accepted: refinement completes, the elevator doors close, then greetd starts the session.
    Timer {
        id: granted
        interval: root.reducedMotion ? 0 : 1300
        onTriggered: {
            root.leaving = true;
            launch.restart();
        }
    }
    Timer {
        id: launch
        interval: root.reducedMotion ? 0 : 1450
        // greetd joins cmd with spaces and runs it through /bin/sh itself.
        // Passing an argv-style sh -c here loses the command's quoting and
        // executes only the inner `exec`, immediately ending the session.
        onTriggered: Greetd.launch([root.session.exec], ["XDG_SESSION_TYPE=wayland"], true)
    }

    FileView {
        id: stateFile
        path: root.statePath
        atomicWrites: true
        printErrors: false
        onLoaded: {
            try {
                root.saved = JSON.parse(text()) || {};
            } catch (error) {
                root.saved = {};
            }
            root.restore();
        }
    }

    FileView {
        path: root.passwdPath
        onLoaded: root.parseUsers(text())
    }

    Process {
        running: true
        command: ["/bin/sh", "-c", "for f in \"$1\"/*.desktop; do [ -f \"$f\" ] || continue; "
            + "grep -qi '^NoDisplay=true' \"$f\" && continue; "
            + "n=$(sed -n 's/^Name=//p' \"$f\" | head -n1); e=$(sed -n 's/^Exec=//p' \"$f\" | head -n1); "
            + "[ -n \"$n\" ] && [ -n \"$e\" ] && printf '%s\\t%s\\n' \"$n\" \"$e\"; done", "sh", root.sessionsDir]
        stdout: StdioCollector {
            onStreamFinished: root.parseSessions(text)
        }
    }

    LockPalette {
        id: colours
        path: Quickshell.env("WYSUN_GREETER_SCHEME") || "/etc/wysun/greeter/scheme.json"
    }

    Variants {
        model: Quickshell.screens

        PanelWindow {
            id: surface

            required property ShellScreen modelData
            readonly property bool primary: modelData === Quickshell.screens[0]

            screen: modelData
            anchors.left: true
            anchors.right: true
            anchors.top: true
            anchors.bottom: true
            exclusionMode: ExclusionMode.Ignore
            color: colours.surface
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.namespace: "wysun-greeter"
            WlrLayershell.keyboardFocus: primary ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

            LockScene {
                anchors.fill: parent
                scheme: colours
                takesInput: surface.primary
                authState: root.authState
                detail: root.message.length ? root.message : root.hints
                leaving: root.leaving
                username: root.user
                mono: Quickshell.env("WYSUN_GREETER_MONO") || "monospace"
                exitStyle: "elevator"
                shaderDir: Quickshell.env("WYSUN_LOCK_SHADERS") || ""
                reducedMotion: root.reducedMotion
                onSubmitted: password => root.submit(password)
                onNavigate: action => root.navigate(action)
                Component.onCompleted: if (surface.primary) focusInput()
            }
        }
    }
}
