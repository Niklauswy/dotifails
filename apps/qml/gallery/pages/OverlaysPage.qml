// Menus, dialogs, snackbars and tooltips (they draw in the gallery's OverlayLayer).
import QtQuick
import WysunM3
import ".."

Page {
    id: page

    Section {
        title: "Menú"

        Button {
            id: menuButton

            type: "tonal"
            text: "Abrir menú"
            icon: "more_vert"
            onClicked: menu.popup(menuButton, 0, menuButton.height)
        }

        Menu {
            id: menu

            host: page.overlay
            model: [{id: "open", text: "Abrir", icon: "open_in_new", shortcut: "Enter"}, {id: "rename", text: "Renombrar", icon: "edit", shortcut: "F2"}, {id: "copy", text: "Copiar", icon: "content_copy", shortcut: "Ctrl+C"}, {divider: true}, {id: "trash", text: "Mover a la papelera", icon: "delete", shortcut: "Supr"}]
            onTriggered: id => page.snackbars?.show("Menú: " + id)
        }

        Surface {
            width: Metrics.menuMaxWidth * 0.8
            height: Metrics.menuItemHeight * 2
            radius: Theme.rounding.extraSmall ?? 0
            container: Theme.m3surfaceContainer
            color: container
            level: Metrics.menuElevation

            Column {
                width: parent.width

                MenuItem {
                    width: parent.width
                    entry: ({id: "a", text: "MenuItem suelto", icon: "label"})
                }
                MenuItem {
                    width: parent.width
                    entry: ({id: "b", text: "Deshabilitado", icon: "block", disabled: true})
                }
            }
        }
    }

    Section {
        title: "Diálogo"

        Button {
            text: "Borrar archivos…"
            icon: "delete"
            onClicked: dialog.open()
        }

        Dialog {
            id: dialog

            host: page.overlay
            icon: "delete"
            title: "¿Mover 3 elementos a la papelera?"
            message: "Podrás recuperarlos desde la papelera durante 30 días."
            actions: [{id: "cancel", text: "Cancelar"}, {id: "trash", text: "Mover", primary: true}]
            onAccepted: id => page.snackbars?.show({text: id === "trash" ? "3 elementos movidos a la papelera" : "Cancelado", action: id === "trash" ? "Deshacer" : ""})
        }
    }

    Section {
        title: "Snackbar"

        Button {
            type: "outlined"
            text: "Mostrar snackbar"
            onClicked: page.snackbars?.show({text: "Copiado al portapapeles"})
        }
        Button {
            type: "outlined"
            text: "Con acción"
            onClicked: page.snackbars?.show({text: "Archivo borrado", action: "Deshacer", closable: true})
        }
        Snackbar {
            text: "Vista previa de un snackbar"
            actionText: "Acción"
        }
    }

    Section {
        title: "Tooltips"

        IconButton {
            icon: "info"

            Tooltip {
                text: "Información"
                host: page.overlay
            }
        }
        IconButton {
            icon: "help"

            Tooltip {
                rich: true
                title: "Tooltip enriquecido"
                text: "Explica algo con más detalle y puede ocupar varias líneas."
                host: page.overlay
            }
        }
    }
}
