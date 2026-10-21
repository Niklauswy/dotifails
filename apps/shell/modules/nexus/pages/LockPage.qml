pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Lock screen and idle timers; applied live by `wysun-idle` (no session restart).
PageBase {
    id: root

    readonly property var minutes: [0, 1, 5, 10, 15, 30, 60]
    readonly property var choices: minutes.map(m => ({value: m, label: m === 0 ? "Never" : m + " min"}))
    property int lockMinutes: 0
    property int displayOffMinutes: 0
    property bool lockBeforeSleep: true
    property string status: ""
    property bool failed: false

    function load(): void {
        getProc.running = true;
    }

    function save(key: string, value: string): void {
        setProc.command = ["wysun-idle", "set", key, value];
        setProc.running = true;
    }

    title: "Lock & Idle"
    Component.onCompleted: load()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        Process {
            id: getProc

            command: ["wysun-idle", "get"]
            stdout: StdioCollector {
                onStreamFinished: {
                    try {
                        const prefs = JSON.parse(text);
                        root.lockMinutes = prefs.lock_minutes;
                        root.displayOffMinutes = prefs.display_off_minutes;
                        root.lockBeforeSleep = prefs.lock_before_sleep;
                    } catch (error) {
                        root.status = "Could not read the idle preferences.";
                        root.failed = true;
                    }
                }
            }
        }

        Process {
            id: setProc

            stdout: StdioCollector {
                onStreamFinished: {
                    root.load();
                    root.status = "Saved and applied to this session.";
                    root.failed = false;
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

        SectionHeader {
            first: true
            text: "Inactivity"
        }

        StyledText {
            Layout.fillWidth: true
            Layout.bottomMargin: Tokens.spacing.small
            text: "Changes apply immediately; your session and open apps are not affected."
            wrapMode: Text.Wrap
            font: Tokens.font.body.small
            color: Colours.palette.m3onSurfaceVariant
        }

        OptionRow {
            first: true
            label: "Lock after inactivity"
            options: root.choices
            current: root.lockMinutes
            onPicked: value => root.save("lock_minutes", String(value))
        }

        OptionRow {
            last: true
            label: "Turn off displays after inactivity"
            options: root.choices
            current: root.displayOffMinutes
            onPicked: value => root.save("display_off_minutes", String(value))
        }

        SectionHeader {
            text: "Sleep"
        }

        ToggleRow {
            text: "Lock before sleep"
            subtext: "Lock the screen when the system suspends"
            checked: root.lockBeforeSleep
            onToggled: root.save("lock_before_sleep", checked ? "true" : "false")
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                text: "Lock now"
                onClicked: Quickshell.execDetached(["wysun-lock"])
            }
        }
    }
}
