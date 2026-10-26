// F1: the keyboard shortcuts of Wysun Music, as a dialog.
import QtQuick
import WysunM3

Dialog {
    id: root

    readonly property var rows: [
        ["Reproducir / pausar", "Espacio · Ctrl+Espacio"],
        ["Anterior / siguiente", "Ctrl+← / Ctrl+→"],
        ["Volumen ±5", "Ctrl+↑ / Ctrl+↓"],
        ["Silenciar", "M"],
        ["Aleatorio", "Ctrl+S"],
        ["Cambiar repetición", "Ctrl+R"],
        ["Tus me gusta (actual)", "Ctrl+Mayús+F"],
        ["Buscar", "Ctrl+F · Ctrl+K"],
        ["Limpiar / cerrar", "Esc"],
        ["Atrás / adelante", "Alt+← / Alt+→"],
        ["Ahora suena · Letra · Cola", "Ctrl+P · Ctrl+L · Ctrl+Q"],
        ["Nueva playlist", "Ctrl+N"],
        ["Importar archivos", "Ctrl+O"],
        ["Inicio · Tus me gusta · Artistas · Añadir música · Importar", "Alt+1 … Alt+5"],
        ["Enfocar el contenido", "Ctrl+J"],
        ["En la lista: reproducir · artista · me gusta · menú", "Enter · Ctrl+Enter · F · Menú"],
        ["En la letra: elegir línea y saltar", "↑ / ↓ · Enter"],
        ["En los resultados de descarga: descargar selección", "Ctrl+Enter"]
    ]

    objectName: "shortcutSheet"
    title: "Atajos de teclado"
    icon: "keyboard"
    modal: false
    actions: [{id: "close", text: "Cerrar", primary: true}]

    Column {
        width: parent ? parent.width : 0
        spacing: Theme.spacing.small ?? 0

        Repeater {
            model: root.rows

            Item {
                required property var modelData

                width: parent.width
                height: Math.max(what.implicitHeight, keys.implicitHeight)

                Label {
                    id: what

                    width: parent.width * 0.55
                    role: "body.medium"
                    text: modelData[0]
                    wrapMode: Text.Wrap
                }
                Label {
                    id: keys

                    anchors.right: parent.right
                    width: parent.width * 0.42
                    role: "label.large"
                    text: modelData[1]
                    color: Theme.m3primary
                    horizontalAlignment: Text.AlignRight
                    wrapMode: Text.Wrap
                }
            }
        }
    }
}
