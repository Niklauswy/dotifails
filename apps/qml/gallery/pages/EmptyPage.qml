// Empty and first-run states: an expressive emblem that springs in, a title, a message and one action.
import QtQuick
import WysunM3
import ".."

Page {
    id: page

    property int replay: 0

    Section {
        title: "Estados vacíos"
        note: "Pasa el ratón por el emblema. «Repetir» vuelve a crearlos para ver la entrada."

        Button {
            type: "text"
            text: "Repetir"
            icon: "replay"
            onClicked: page.replay++
        }
    }

    Section {
        Repeater {
            // A new array on every replay makes the Repeater create the states again (and replay their entrance).
            model: page.replay >= 0 ? [["cookie", "folder_open", "Carpeta vacía", "Arrastra archivos aquí o crea una carpeta.", "Nueva carpeta"], ["flower", "library_music", "Tu biblioteca está vacía", "Añade una carpeta de música para empezar.", "Añadir carpeta"], ["sunny", "search_off", "Sin resultados", "Prueba con otras palabras.", ""]] : []

            Card {
                required property var modelData

                width: Math.min(page.width - 2 * (Theme.padding.extraLarge ?? 0), Metrics.textFieldMinWidth * 1.6)
                height: Metrics.topAppBarLarge * 2.4
                variant: "outlined"

                EmptyState {
                    anchors.fill: parent
                    emblemShape: modelData[0]
                    icon: modelData[1]
                    title: modelData[2]
                    message: modelData[3]
                    actionText: modelData[4]
                    onAction: page.snackbars?.show(modelData[4])
                }
            }
        }
    }
}
