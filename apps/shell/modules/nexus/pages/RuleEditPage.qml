pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Add, edit or remove one window rule; saved at once like the rest of the desktop settings.
PageBase {
    id: root

    readonly property var context: nState.selectedRule
    readonly property bool editing: (context?.index ?? -1) >= 0
    property string appClass: context?.rule?.class ?? ""
    property string windowState: context?.rule?.state ?? "tiled"
    property string workspace: context?.rule?.desktop ?? ""
    property bool center: context?.rule?.center ?? false
    property bool border: context?.rule?.border ?? true
    property string status: "Las reglas se aplican a las ventanas nuevas."
    property bool failed: false

    function save(remove: bool): void {
        const list = (context?.rules ?? []).slice();
        const rule = {class: appClass.trim(), state: windowState, desktop: workspace.trim(), center: center, border: border};
        if (remove)
            list.splice(context.index, 1);
        else if (editing)
            list[context.index] = rule;
        else
            list.push(rule);
        DesktopBridge.call("desktop.apply", {rules: list}, () => nState.closeSubPage(), message => {
            root.status = message;
            root.failed = true;
        });
    }

    title: editing ? "Editar regla" : "Nueva regla"
    isSubPage: true

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        TextFieldRow {
            first: true
            label: "Clase de aplicación"
            subtext: "Por ejemplo: Code, Gimp, com.mitchellh.ghostty"
            value: root.appClass
            maximumLength: 120
            onValueEdited: value => root.appClass = value
        }

        OptionRow {
            label: "Estado"
            options: [{value: "tiled", label: "Mosaico"}, {value: "floating", label: "Flotante"}, {value: "fullscreen", label: "Pantalla completa"}]
            current: root.windowState
            onPicked: value => root.windowState = value
        }

        TextFieldRow {
            label: "Escritorio"
            subtext: "Opcional · 1, 2…"
            value: root.workspace
            maximumLength: 40
            smallField: true
            onValueEdited: value => root.workspace = value
        }

        ToggleRow {
            text: "Centrar la ventana"
            checked: root.center
            onToggled: root.center = checked
        }

        ToggleRow {
            last: true
            text: "Mostrar borde"
            checked: root.border
            onToggled: root.border = checked
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                text: "Guardar regla"
                disabled: !root.appClass.trim()
                onClicked: root.save(false)
            }

            ActionButton {
                visible: root.editing
                type: TextButton.Tonal
                text: "Eliminar"
                onClicked: root.save(true)
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Cancelar"
                onClicked: root.nState.closeSubPage()
            }
        }
    }
}
