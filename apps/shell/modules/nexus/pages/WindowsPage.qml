pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Window behaviour of the compositor and per-application window rules.
PageBase {
    id: root

    readonly property var stateNames: ({tiled: "Mosaico", floating: "Flotante", fullscreen: "Pantalla completa"})
    property var values: ({})
    property var rules: []
    property var schema: ({})
    property string status: ""
    property bool failed: false
    property bool dirty: false

    function load(rulesOnly: bool): void {
        DesktopBridge.call("desktop.state", {}, data => {
            root.rules = data.rules;
            root.schema = data.schema;
            if (!rulesOnly || !root.dirty) {
                root.values = data.values;
                root.dirty = false;
            }
        }, message => {
            root.status = message;
            root.failed = true;
        });
    }

    function setValue(key: string, value: var): void {
        const copy = Object.assign({}, values);
        copy[key] = String(value);
        values = copy;
        dirty = true;
    }

    function apply(): void {
        status = "Aplicando…";
        failed = false;
        DesktopBridge.call("desktop.apply", {values: values, rules: rules}, data => {
            root.values = data.values;
            root.rules = data.rules;
            root.dirty = false;
            root.status = "Cambios aplicados y guardados para el próximo inicio.";
        }, message => {
            root.status = "No se aplicó el cambio: " + message;
            root.failed = true;
        });
    }

    function editRule(index: int): void {
        nState.selectedRule = {index: index, rules: rules, rule: index >= 0 ? rules[index] : null};
        nState.openSubPage(6);
    }

    title: "Ventanas"
    isSubPage: true
    Component.onCompleted: load(false)
    onVisibleChanged: if (visible && status) load(true)

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: "Espacio y bordes"
        }

        StepperRow {
            first: true
            label: "Separación entre ventanas"
            subtext: "Píxeles"
            from: root.schema.window_gap?.low ?? 0
            to: root.schema.window_gap?.high ?? 80
            value: Number(root.values.window_gap ?? 0)
            onMoved: value => root.setValue("window_gap", Math.round(value))
        }

        StepperRow {
            label: "Grosor del borde"
            subtext: "Píxeles"
            from: root.schema.border_width?.low ?? 0
            to: root.schema.border_width?.high ?? 12
            value: Number(root.values.border_width ?? 0)
            onMoved: value => root.setValue("border_width", Math.round(value))
        }

        StepperRow {
            label: "Proporción al dividir"
            subtext: "0,1 – 0,9"
            from: 0
            to: 90
            stepSize: 5
            value: Math.round(Number(root.values.split_ratio ?? 0.5) * 100)
            onMoved: value => root.setValue("split_ratio", Math.max(0.1, Math.min(0.9, value / 100)))
        }

        TextFieldRow {
            label: "Borde de la ventana activa"
            subtext: "#RRGGBB"
            value: root.values.focused_border_color ?? ""
            maximumLength: 7
            smallField: true
            onValueEdited: value => root.setValue("focused_border_color", value)
        }

        TextFieldRow {
            last: true
            label: "Borde de las demás ventanas"
            subtext: "#RRGGBB"
            value: root.values.normal_border_color ?? ""
            maximumLength: 7
            smallField: true
            onValueEdited: value => root.setValue("normal_border_color", value)
        }

        SectionHeader {
            text: "Puntero"
        }

        ToggleRow {
            first: true
            text: "Enfocar al pasar el puntero"
            checked: root.values.focus_follows_pointer === "true"
            onToggled: root.setValue("focus_follows_pointer", checked)
        }

        ToggleRow {
            last: true
            text: "Mover el puntero con el foco"
            checked: root.values.pointer_follows_focus === "true"
            onToggled: root.setValue("pointer_follows_focus", checked)
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                text: "Aplicar cambios"
                disabled: !root.dirty
                onClicked: root.apply()
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Recargar"
                onClicked: root.load(false)
            }
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        SectionHeader {
            text: "Reglas de ventanas"
        }

        Repeater {
            model: root.rules

            RowButton {
                required property var modelData
                required property int index

                first: index === 0
                last: false
                icon: "rule"
                text: modelData.class
                subtext: (root.stateNames[modelData.state] ?? modelData.state) + (modelData.desktop ? " · escritorio " + modelData.desktop : "") + (modelData.center ? " · centrada" : "") + (modelData.border === false ? " · sin borde" : "")
                trailingIcon: "edit"
                onClicked: root.editRule(index)
            }
        }

        RowButton {
            first: root.rules.length === 0
            last: true
            icon: "add"
            text: "Añadir regla"
            subtext: "Define cómo se abre una aplicación"
            onClicked: root.editRule(-1)
        }
    }
}
