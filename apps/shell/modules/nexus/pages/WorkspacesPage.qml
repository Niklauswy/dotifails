pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Fixed workspaces 1–10 per screen.
PageBase {
    id: root

    property string selectedOutput: ""
    property bool busy: false
    readonly property var displayRows: rows.filter(r => (r.assigned || r.monitor) === selectedOutput)
    property var rows: []
    property var outputs: []
    property string status: ""
    property bool failed: false
    property string confirmReset: ""

    function adopt(data: var): void {
        rows = data.rows;
        outputs = data.outputs;
        if (!outputs.includes(selectedOutput)) selectedOutput = outputs[0] ?? "";
    }

    function load(): void {
        DisplayBridge.call("workspaces.state", {}, data => root.adopt(data), message => {
            status = message;
            failed = true;
        });
    }

    function edit(args: var, success: string): void {
        if (busy) return;
        busy = true;
        DisplayBridge.call("workspaces.edit", args, data => {
            root.busy = false;
            root.adopt(data);
            root.status = success;
            root.failed = false;
        }, message => {
            root.busy = false;
            root.status = message;
            root.failed = true;
        });
    }

    title: "Workspaces"
    Component.onCompleted: { selectedOutput = nState.screen?.name ?? ""; load(); }

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: "Workspaces by display"
        }

        StyledText {
            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small
            Layout.bottomMargin: Tokens.spacing.small
            wrapMode: Text.Wrap
            text: "Keep workspace assignments across sessions. Select a display to manage its workspaces. Workspace 10 appears as 0 in the taskbar (Super+0)."
            color: Colours.palette.m3onSurfaceVariant
            font: Tokens.font.label.small
        }

        Flow {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            Repeater {
                model: root.outputs

                ActionButton {
                    required property string modelData
                    readonly property var assigned: root.rows.filter(r => (r.assigned || r.monitor) === modelData)
                    text: modelData + "  ·  " + assigned.length + (assigned.length === 1 ? " workspace" : " workspaces")
                    type: root.selectedOutput === modelData ? TextButton.Filled : TextButton.Tonal
                    onClicked: root.selectedOutput = modelData
                }
            }
        }

        SectionHeader {
            text: root.selectedOutput || "No connected displays"
        }

        StyledText {
            Layout.fillWidth: true
            visible: root.displayRows.length === 0
            text: root.outputs.length ? "No workspaces assigned to this display. Add one below." : "Connect a display, then refresh to manage workspaces."
            font: Tokens.font.body.small
            color: Colours.palette.m3onSurfaceVariant
            wrapMode: Text.Wrap
        }

        Repeater {
            model: root.displayRows

            OptionRow {
                id: row

                required property var modelData
                required property int index

                first: index === 0
                last: index === root.displayRows.length - 1
                label: "Workspace " + (modelData.number || modelData.label)
                subtext: modelData.windows + (modelData.windows === 1 ? " window" : " windows") + (modelData.active ? " · active" : "") + (modelData.fixed ? "" : " · temporary") + (modelData.number === 10 ? " · Super+0" : "")
                enabled: !root.busy && !!modelData.number
                options: root.outputs.map(o => ({value: o, label: o}))
                current: modelData.assigned || modelData.monitor
                onPicked: value => {
                    if (modelData.number)
                        root.edit({action: "assign", number: modelData.number, monitor: value}, "Workspace " + (modelData.number || modelData.label) + " assigned to " + value + ".");
                    else
                        root.status = "Named workspaces cannot be pinned to a numbered slot.";
                }
            }
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        SectionHeader {
            text: "Add a workspace"
        }

        Repeater {
            model: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].filter(n => !root.rows.some(r => r.number === n))

            OptionRow {
                id: free

                required property int modelData
                required property int index

                first: index === 0
                enabled: !root.busy
                last: index === [1,2,3,4,5,6,7,8,9,10].filter(n => !root.rows.some(r => r.number === n)).length - 1
                label: "Assign workspace " + modelData
                subtext: "Choose the display where it will open"
                options: root.outputs.map(o => ({value: o, label: o}))
                current: ""
                fallbackText: "Display…"
                onPicked: value => root.edit({action: "assign", number: free.modelData, monitor: value}, "Workspace " + free.modelData + " assigned to " + value + ".")
            }
        }

        StyledText {
            Layout.fillWidth: true
            visible: [1,2,3,4,5,6,7,8,9,10].every(n => root.rows.some(r => r.number === n))
            text: "All ten workspace slots are assigned. Move a workspace using its display menu above."
            color: Colours.palette.m3onSurfaceVariant
            font: Tokens.font.body.small
            wrapMode: Text.Wrap
        }

        RowLayout {
            enabled: !root.busy
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                type: TextButton.Tonal
                text: "Refresh"
                onClicked: root.load()
            }

            ActionButton {
                type: TextButton.Tonal
                text: root.confirmReset ? "Confirm reset" : "Reset assignments"
                onClicked: {
                    if (root.confirmReset) {
                        root.confirmReset = "";
                        root.edit({action: "reset"}, "Automatic assignments restored.");
                    } else {
                        root.confirmReset = "yes";
                        resetTimer.restart();
                    }
                }
            }
        }

        SectionHeader {
            visible: root.displayRows.some(r => r.fixed && r.number && r.windows === 0)
            text: "Remove empty workspaces"
        }

        Repeater {
            model: root.displayRows.filter(r => r.fixed && r.number && r.windows === 0)

            RowButton {
                required property var modelData
                required property int index

                first: index === 0
                enabled: !root.busy
                last: index === root.displayRows.filter(r => r.fixed && r.number && r.windows === 0).length - 1
                icon: "delete"
                text: "Remove workspace " + (modelData.number || modelData.label) + " (empty)"
                subtext: "Remove its persistent assignment"
                onClicked: root.edit({action: "remove", number: modelData.number}, "Workspace " + (modelData.number || modelData.label) + " removed.")
            }
        }

        Timer {
            id: resetTimer

            interval: 5000
            onTriggered: root.confirmReset = ""
        }
    }
}
