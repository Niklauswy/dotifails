pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Applications started with the session, and the state of the base desktop services.
PageBase {
    id: root

    property var entries: []
    property var services: []
    property string status: ""
    property bool failed: false
    property string newName: ""
    property string newCommand: ""

    function adopt(data: var): void {
        entries = data.entries;
        services = data.services;
    }

    function run(action: string, args: var, success: string): void {
        DesktopBridge.call(action, args, data => {
            root.adopt(data);
            root.status = success;
            root.failed = false;
        }, message => {
            root.status = message;
            root.failed = true;
        });
    }

    title: "Inicio y aplicaciones"
    isSubPage: true
    Component.onCompleted: DesktopBridge.call("startup.state", {}, data => adopt(data), message => {
        status = message;
        failed = true;
    })

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: "Aplicaciones al iniciar sesión"
        }

        Repeater {
            model: root.entries

            ToggleRow {
                required property var modelData
                required property int index

                first: index === 0
                last: index === root.entries.length - 1
                text: modelData.name
                subtext: modelData.command
                checked: modelData.managed && modelData.enabled
                onToggled: root.run("startup.toggle", {id: modelData.id, enabled: checked}, "Cambio guardado para el próximo inicio de sesión.")
            }
        }

        SectionHeader {
            text: "Añadir aplicación"
        }

        TextFieldRow {
            first: true
            label: "Nombre"
            value: root.newName
            maximumLength: 80
            onValueEdited: value => root.newName = value
        }

        TextFieldRow {
            last: true
            label: "Comando"
            subtext: "Programa y argumentos, por ejemplo nm-applet"
            value: root.newCommand
            onValueEdited: value => root.newCommand = value
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.small
            spacing: Tokens.spacing.small

            ActionButton {
                text: "Añadir al inicio"
                disabled: !root.newName.trim() || !root.newCommand.trim()
                onClicked: {
                    root.run("startup.add", {name: root.newName, command: root.newCommand}, "Aplicación añadida al próximo inicio.");
                    root.newName = "";
                    root.newCommand = "";
                }
            }
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        SectionHeader {
            text: "Servicios del escritorio"
        }

        Repeater {
            model: root.services

            InfoRow {
                required property var modelData
                required property int index

                first: index === 0
                last: index === root.services.length - 1
                label: modelData.name
                value: modelData.running ? "Activo" : "Detenido"
                icon: modelData.running ? "check_circle" : "error"
                iconColour: modelData.running ? Colours.palette.m3primary : Colours.palette.m3error
            }
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                type: TextButton.Tonal
                text: "Recargar shell"
                onClicked: {
                    Quickshell.execDetached(["wysun", "shell", "reload-preferences"]);
                    root.status = "Shell recargado.";
                    root.failed = false;
                }
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Editar Hyprland"
                onClicked: DesktopBridge.call("file.open", {path: Quickshell.env("HOME") + "/.config/wysun/hyprland.lua"}, () => {}, message => {
                    root.status = message;
                    root.failed = true;
                })
            }
        }
    }
}
