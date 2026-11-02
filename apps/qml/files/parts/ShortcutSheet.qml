// F1: the keyboard shortcuts of Wysun Files, as a dialog.
import QtQuick
import WysunM3

Dialog {
    id: root

    readonly property var rows: [
        ["Opciones del elemento actual", "Alt+K · Menú"],
        ["Filtrar nombres", "Ctrl+F · escribir"],
        ["Escribir una ruta", "Ctrl+L"],
        ["Nueva pestaña / cerrar pestaña", "Ctrl+T / Ctrl+W"],
        ["Cambiar de pestaña", "Ctrl+Tab · Ctrl+RePág / AvPág"],
        ["Historial", "Alt+← / Alt+→"],
        ["Carpeta superior", "Alt+↑ · Retroceso · ← en la lista"],
        ["Carpeta personal", "Alt+Inicio"],
        ["Cuadrícula / lista", "Ctrl+1 / Ctrl+2"],
        ["Archivos ocultos", "Ctrl+H"],
        ["Vista previa automática", "Ctrl+I"],
        ["Ampliar la vista previa", "Espacio"],
        ["Pantalla completa (vídeo)", "F"],
        ["Copiar, cortar, pegar", "Ctrl+C / X / V"],
        ["Cambiar nombre", "F2"],
        ["Enviar a la papelera", "Supr"],
        ["Nueva carpeta", "Ctrl+Mayús+N"],
        ["Copiar ruta", "Ctrl+Mayús+C"],
        ["Cerrar o quitar selección", "Esc"],
        ["Cerrar la ventana", "Ctrl+Q"]
    ]

    objectName: "shortcutSheet"
    title: "Atajos de teclado"
    icon: "keyboard"
    modal: false
    actions: [{id: "close", text: "Cerrar", primary: true}]

    Grid {
        columns: 2
        columnSpacing: Theme.spacing.large ?? 0
        rowSpacing: Theme.spacing.extraSmall ?? 0

        Repeater {
            model: root.rows.reduce((all, row) => all.concat([{text: row[0]}, {text: row[1], keys: true}]), [])

            Label {
                required property var modelData

                role: "body.medium"
                text: modelData.text
                color: modelData.keys ? Theme.m3onSurfaceVariant : Theme.m3onSurface
            }
        }
    }
}
