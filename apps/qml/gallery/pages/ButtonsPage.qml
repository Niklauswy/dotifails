// Buttons: common buttons in their five types, toggles, icon buttons, FABs and segmented buttons.
import QtQuick
import WysunM3
import ".."

Page {
    Section {
        title: "Botones"
        note: "filled > tonal > outlined/elevated > text, por énfasis. Al pulsar, la esquina se transforma."

        Button {
            text: "Filled"
        }
        Button {
            type: "tonal"
            text: "Tonal"
            icon: "add"
        }
        Button {
            type: "outlined"
            text: "Outlined"
        }
        Button {
            type: "elevated"
            text: "Elevated"
            icon: "star"
        }
        Button {
            type: "text"
            text: "Text"
        }
        Button {
            text: "Deshabilitado"
            disabled: true
        }
        Button {
            type: "tonal"
            checkable: true
            text: "Conmutable"
            icon: "push_pin"
        }
    }

    Section {
        title: "Botones de icono"

        IconButton {
            icon: "more_vert"
        }
        IconButton {
            type: "filled"
            icon: "play_arrow"
        }
        IconButton {
            type: "tonal"
            icon: "shuffle"
        }
        IconButton {
            type: "outlined"
            icon: "share"
        }
        IconButton {
            type: "tonal"
            checkable: true
            icon: "favorite"
            iconChecked: "favorite"
        }
        IconButton {
            icon: "delete"
            disabled: true
        }
    }

    Section {
        title: "FAB"
        note: "La acción principal de la pantalla. El extendido se pliega con extended/expanded."

        Fab {
            size: "small"
            icon: "add"
        }
        Fab {
            icon: "edit"
        }
        Fab {
            size: "large"
            variant: "secondary"
            icon: "create_new_folder"
        }
        Fab {
            id: extended

            extended: true
            variant: "tertiary"
            icon: "upload"
            text: "Subir archivos"
            onClicked: expanded = !expanded
        }
        Fab {
            variant: "surface"
            icon: "navigation"
        }
    }

    Section {
        title: "Botones segmentados"

        SegmentedButtons {
            model: [{value: "list", text: "Lista", icon: "list"}, {value: "grid", text: "Cuadrícula", icon: "grid_view"}, {value: "columns", text: "Columnas", icon: "view_column"}]
            current: "grid"
        }
        SegmentedButtons {
            multiSelect: true
            model: [{value: "img", text: "Imágenes"}, {value: "doc", text: "Documentos"}, {value: "audio", text: "Audio"}]
            selection: ["img"]
        }
    }
}
