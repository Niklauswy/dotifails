pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.components.rows
import qs.services
import qs.modules.nexus.common

// Wysun Drive: which Nextcloud it uploads to, the folder, and the session. Everything goes
// through `wysun drive estado|ajustes|login|logout` (apps/python/wysun_drive/cli.py), so the
// terminal and this page always agree. The app password never reaches the shell.
PageBase {
    id: root

    property string server
    property string folder
    property string user
    property string otherServer
    property bool loaded
    property bool signingIn
    property string status
    property bool failed

    function load(): void {
        stateProc.running = true;
    }

    function saveSettings(): void {
        const next = ["wysun", "drive", "ajustes"];
        if (serverField.text.trim() !== server)
            next.push("--servidor", serverField.text.trim());
        if (folderField.text.trim() !== folder)
            next.push("--carpeta", folderField.text.trim());
        if (next.length === 3)
            return;
        saveProc.command = next;
        saveProc.running = true;
    }

    title: "Wysun Drive"
    Component.onCompleted: load()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        Process {
            id: stateProc

            command: ["wysun", "drive", "estado", "--json"]
            stdout: StdioCollector {
                onStreamFinished: {
                    try {
                        const data = JSON.parse(text);
                        root.server = data.server ?? "";
                        root.folder = data.folder ?? "";
                        root.user = data.user ?? "";
                        root.otherServer = data.other_server ?? "";
                        serverField.text = root.server;
                        folderField.text = root.folder;
                        root.loaded = true;
                    } catch (error) {
                        root.status = Tr.tr("Could not read the Wysun Drive settings.");
                        root.failed = true;
                    }
                }
            }
        }

        Process {
            id: saveProc

            stdout: StdioCollector {
                onStreamFinished: {
                    root.status = Tr.tr("Saved.");
                    root.failed = false;
                    root.load();
                }
            }
            stderr: StdioCollector {
                onStreamFinished: {
                    if (text.trim()) {
                        root.status = text.trim();
                        root.failed = true;
                    }
                }
            }
        }

        // The login flow: Nextcloud opens in the browser and this waits until access is granted.
        Process {
            id: loginProc

            command: ["wysun", "drive", "login"]
            stderr: StdioCollector {
                id: loginErr
            }
            onExited: code => {
                root.signingIn = false;
                root.failed = code !== 0;
                root.status = code === 0 ? Tr.tr("Signed in.") : (loginErr.text.trim() || Tr.tr("Sign-in was not completed."));
                root.load();
            }
        }

        Process {
            id: logoutProc

            command: ["wysun", "drive", "logout"]
            onExited: {
                root.status = Tr.tr("Signed out.");
                root.failed = false;
                root.load();
            }
        }

        SectionHeader {
            first: true
            text: Tr.tr("Nextcloud server")
        }

        StyledText {
            Layout.fillWidth: true
            Layout.bottomMargin: Tokens.spacing.small
            text: Tr.tr("Wysun Drive works with any Nextcloud. After changing the server, sign in again. If the browser sign-in fails, create an app password in Nextcloud (Personal settings › Security) and use it instead.")
            wrapMode: Text.Wrap
            font: Tokens.font.body.small
            color: Colours.palette.m3onSurfaceVariant
        }

        StyledTextField {
            id: serverField

            Layout.fillWidth: true
            enabled: root.loaded && !root.signingIn
            placeholderText: "https://cloud.example.com"
            leadingIcon: "cloud"
            supportingText: Tr.tr("Address of your Nextcloud (HTTPS)")
            inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText | Qt.ImhUrlCharactersOnly
            onAccepted: root.saveSettings()
        }

        StyledTextField {
            id: folderField

            Layout.fillWidth: true
            Layout.topMargin: Tokens.spacing.small
            enabled: root.loaded && !root.signingIn
            placeholderText: "Wysun"
            leadingIcon: "folder"
            supportingText: Tr.tr("Folder in your Nextcloud where uploads go")
            inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText
            onAccepted: root.saveSettings()
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.small
            spacing: Tokens.spacing.small

            ActionButton {
                text: Tr.tr("Save")
                enabled: root.loaded && (serverField.text.trim() !== root.server || folderField.text.trim() !== root.folder)
                onClicked: root.saveSettings()
            }
        }

        SectionHeader {
            text: Tr.tr("Account")
        }

        StyledText {
            Layout.fillWidth: true
            text: root.signingIn ? Tr.tr("Approve Wysun Drive in the browser that opened…")
                : root.user ? Tr.tr("Signed in as %1").arg(root.user)
                : root.otherServer ? Tr.tr("The saved session belongs to %1. Sign in to use this server.").arg(root.otherServer)
                : Tr.tr("Not signed in")
            wrapMode: Text.Wrap
            font: Tokens.font.body.medium
            color: root.user ? Colours.palette.m3onSurface : Colours.palette.m3onSurfaceVariant
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.small
            spacing: Tokens.spacing.small

            ActionButton {
                text: root.signingIn ? Tr.tr("Cancel") : root.user ? Tr.tr("Sign in again") : Tr.tr("Sign in")
                enabled: root.loaded
                onClicked: {
                    if (root.signingIn) {
                        loginProc.signal(15);
                        return;
                    }
                    root.status = "";
                    root.signingIn = true;
                    loginProc.running = true;
                }
            }

            ActionButton {
                visible: !!root.user || !!root.otherServer
                enabled: !root.signingIn
                text: Tr.tr("Sign out")
                onClicked: logoutProc.running = true
            }

            ActionButton {
                visible: !root.user
                enabled: !root.signingIn
                text: Tr.tr("Use an app password…")
                // The terminal selector asks for it (key p): the password never passes through the shell.
                onClicked: Quickshell.execDetached(["wysun", "drive", "--terminal"])
            }

            ActionButton {
                text: Tr.tr("Open Wysun Drive")
                onClicked: Quickshell.execDetached(["wysun", "drive", "--terminal"])
            }
        }

        StatusLine {
            text: root.status
            error: root.failed
        }
    }
}
