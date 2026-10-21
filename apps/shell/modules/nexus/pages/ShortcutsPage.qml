pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Global Hyprland shortcuts (editable) plus the shortcuts of Wysun apps, the terminal and Neovim.
PageBase {
    id: root

    readonly property var scopes: ["Todos", "Global", "Conflictos", "Terminal", "Neovim", "Wysun", "Archivos"].map(s => ({value: s, label: s}))
    property var globalRows: []
    property var appRows: []
    property int conflicts: 0
    property string path: ""
    property string query: ""
    property string scope: "Todos"
    property string status: ""
    property bool failed: false
    readonly property var visibleRows: {
        const needle = query.toLowerCase();
        return globalRows.concat(appRows).filter(r => {
            if (scope === "Conflictos" && !r.duplicate)
                return false;
            if (scope !== "Todos" && scope !== "Conflictos" && r.scope !== scope)
                return false;
            return !needle || [r.key, r.title, r.command, r.scope].join(" ").toLowerCase().includes(needle);
        }).slice(0, 200);
    }

    function load(): void {
        DesktopBridge.call("shortcuts.state", {}, data => {
            root.globalRows = data.rows;
            root.conflicts = data.conflicts;
            root.path = data.path;
        }, message => {
            root.status = message;
            root.failed = true;
        });
        DesktopBridge.call("shortcuts.apps", {}, data => root.appRows = data.rows, () => {});
    }

    function edit(row: var): void {
        nState.selectedShortcut = row;
        nState.openSubPage(4);
    }

    title: "Atajos"
    isSubPage: true
    Component.onCompleted: load()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: root.globalRows.length + " globales · " + root.appRows.length + " de aplicaciones · " + (root.conflicts ? root.conflicts + " combinaciones repetidas" : "sin conflictos")
        }

        TextFieldRow {
            first: true
            label: "Buscar"
            subtext: "Teclas, acción o comando"
            value: root.query
            onValueEdited: value => root.query = value
        }

        OptionRow {
            last: true
            label: "Dónde funciona"
            options: root.scopes
            current: root.scope
            onPicked: value => root.scope = value
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.small
            spacing: Tokens.spacing.small

            ActionButton {
                text: "Nuevo atajo global"
                onClicked: root.edit(null)
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Abrir archivo en Vim"
                onClicked: DesktopBridge.call("file.open", {path: root.path}, () => {}, message => {
                    root.status = message;
                    root.failed = true;
                })
            }
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        SectionHeader {
            text: "Atajos"
        }

        Repeater {
            model: root.visibleRows

            RowButton {
                required property var modelData
                required property int index

                first: index === 0
                last: index === root.visibleRows.length - 1
                icon: modelData.duplicate ? "warning" : modelData.editable ? "keyboard" : "lock"
                text: modelData.key + " · " + modelData.title
                subtext: (modelData.error || modelData.command) + " — " + modelData.scope + (modelData.duplicate ? " · combinación repetida" : "")
                trailingIcon: modelData.editable ? "edit" : "open_in_new"
                onClicked: {
                    if (modelData.editable) {
                        root.edit(modelData);
                    } else {
                        DesktopBridge.call("file.open", {path: modelData.path}, () => {}, message => {
                            root.status = message;
                            root.failed = true;
                        });
                    }
                }
            }
        }
    }
}
