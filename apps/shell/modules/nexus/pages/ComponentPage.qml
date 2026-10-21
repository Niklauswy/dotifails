pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Effects, terminal and notification settings, described by the backend schema.
PageBase {
    id: root

    readonly property string kind: nState.desktopKind
    property var rows: []
    property var positions: []
    property var draft: ({})
    property string note: ""
    property string heading: ""
    property string status: ""
    property bool failed: false

    function adopt(data: var): void {
        heading = data.title;
        note = data.note;
        rows = data.rows;
        positions = data.positions.map(p => ({value: p.value, label: p.label}));
        const values = {};
        data.rows.forEach(r => values[r.key] = r.value);
        draft = values;
    }

    function load(): void {
        DesktopBridge.call("component.state", {kind: kind}, data => adopt(data), message => {
            status = message;
            failed = true;
        });
    }

    function setValue(key: string, value: var): void {
        const copy = Object.assign({}, draft);
        copy[key] = value;
        draft = copy;
    }

    function apply(): void {
        status = "Aplicando…";
        failed = false;
        DesktopBridge.call("component.apply", {kind: kind, values: draft}, data => {
            adopt(data);
            status = kind === "terminal" ? "Configuración guardada. Abre una terminal nueva o recarga Ghostty." : "Cambios aplicados.";
        }, message => {
            status = message;
            failed = true;
        });
    }

    title: heading || "Ajustes"
    isSubPage: true
    Component.onCompleted: load()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        StyledText {
            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small
            Layout.bottomMargin: Tokens.spacing.small
            wrapMode: Text.Wrap
            text: root.note
            color: Colours.palette.m3outline
            font: Tokens.font.label.small
        }

        Repeater {
            model: root.rows

            Loader {
                id: field

                required property var modelData
                required property int index
                readonly property bool isFirst: index === 0
                readonly property bool isLast: index === root.rows.length - 1

                Layout.fillWidth: true
                sourceComponent: {
                    switch (modelData.type) {
                    case "bool":
                    case "fixed":
                        return toggleComp;
                    case "int":
                    case "float":
                        return stepperComp;
                    case "position":
                        return positionComp;
                    default:
                        return textComp;
                    }
                }
            }
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                text: "Aplicar cambios"
                onClicked: root.apply()
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Recargar"
                onClicked: root.load()
            }

            ActionButton {
                visible: root.kind === "notifications"
                type: TextButton.Tonal
                text: "Probar notificación"
                onClicked: Quickshell.execDetached(["notify-send", "Wysun · Notificaciones", "Así se ven tus avisos actuales."])
            }
        }

        Component {
            id: toggleComp

            ToggleRow {
                readonly property var cfg: (parent as Loader).modelData
                first: (parent as Loader).isFirst
                last: (parent as Loader).isLast
                text: cfg.label
                checked: root.draft[cfg.key] ?? false
                disabled: cfg.type === "fixed"
                onToggled: root.setValue(cfg.key, checked)
            }
        }

        Component {
            id: stepperComp

            StepperRow {
                readonly property var cfg: (parent as Loader).modelData
                first: (parent as Loader).isFirst
                last: (parent as Loader).isLast
                label: cfg.label
                subtext: cfg.type === "float" && cfg.high <= 1 ? "%" : cfg.suffix.trim()
                from: cfg.type === "float" && cfg.high <= 1 ? Math.round(cfg.low * 100) : cfg.low
                to: cfg.type === "float" && cfg.high <= 1 ? Math.round(cfg.high * 100) : cfg.high
                stepSize: cfg.type === "float" ? (cfg.high <= 1 ? 5 : 1) : (cfg.high > 1000 ? 1000 : 1)
                value: cfg.type === "float" && cfg.high <= 1 ? Math.round((root.draft[cfg.key] ?? 0) * 100) : (root.draft[cfg.key] ?? 0)
                onMoved: value => root.setValue(cfg.key, cfg.type === "float" && cfg.high <= 1 ? value / 100 : value)
            }
        }

        Component {
            id: positionComp

            OptionRow {
                readonly property var cfg: (parent as Loader).modelData
                first: (parent as Loader).isFirst
                last: (parent as Loader).isLast
                label: cfg.label
                options: root.positions
                current: root.draft[cfg.key]
                onPicked: value => root.setValue(cfg.key, value)
            }
        }

        Component {
            id: textComp

            TextFieldRow {
                readonly property var cfg: (parent as Loader).modelData
                first: (parent as Loader).isFirst
                last: (parent as Loader).isLast
                label: cfg.label
                subtext: cfg.type === "color" ? "#RRGGBB" : ""
                value: String(root.draft[cfg.key] ?? "")
                onValueEdited: value => root.setValue(cfg.key, value)
            }
        }
    }
}
