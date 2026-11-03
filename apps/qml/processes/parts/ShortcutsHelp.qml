// «?»: every keyboard shortcut of Wysun Processes in two columns.
import QtQuick
import WysunM3

Dialog {
    id: root

    icon: "keyboard"
    title: "Atajos de teclado"
    actions: [{id: "close", text: "Cerrar", primary: true}]

    Grid {
        columns: 2
        columnSpacing: Theme.spacing.extraLarge ?? 0
        rowSpacing: Theme.spacing.extraSmall ?? 0

        Repeater {
            model: [
                ["Buscar", "/  o  Ctrl F"], ["Paleta de acciones", "Ctrl K"],
                ["Mover la selección", "↑ ↓  ·  J K"], ["Primero · último", "G  ·  ⇧G"],
                ["Abrir o cerrar grupo", "→ ←"], ["Cambiar la vista", "V"],
                ["Terminar", "Supr"], ["Forzar el cierre", "⇧ Supr"],
                ["Pausar o reanudar", "P"], ["Prioridad", "+  −"],
                ["Ir a su ventana", "W"], ["Localizar en pantalla", "L"],
                ["Copiar PID", "Y"], ["Ordenar por columna", "S"],
                ["Mis procesos · todos", "U"], ["Congelar los datos", "Espacio"],
                ["Panel de detalle", "I"], ["Pestañas del detalle", "[  ]"],
                ["Secciones", "1 … 5"], ["Esta ayuda", "?"]
            ]

            Row {
                required property var modelData

                width: Metrics.dialogMinWidth
                height: Metrics.chipHeight

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width * 0.58
                    text: parent.modelData[0]
                    role: "body.medium"
                }

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    text: parent.modelData[1]
                    role: "label.large"
                    font.family: Theme.font.family?.mono ?? ""
                    color: Theme.m3primary
                }
            }
        }
    }
}
