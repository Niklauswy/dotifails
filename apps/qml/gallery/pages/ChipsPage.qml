// Chips, badges, dividers, progress and the expressive shapes (ShapeEmblem).
import QtQuick
import WysunM3
import ".."

Page {
    id: page

    Section {
        title: "Chips"

        Chip {
            text: "Abrir con…"
            icon: "open_in_new"
        }
        Chip {
            kind: "filter"
            text: "Imágenes"
        }
        Chip {
            kind: "filter"
            text: "Esta semana"
            selected: true
        }
        Chip {
            kind: "input"
            text: "vacaciones.png"
            icon: "image"
            onRemoved: page.snackbars?.show({text: "Quitado vacaciones.png", action: "Deshacer"})
        }
        Chip {
            kind: "suggestion"
            text: "Buscar «mar»"
        }
    }

    Section {
        title: "Insignias y divisores"

        Icon {
            name: "notifications"

            Badge {
                x: parent.width - width / 2
                y: -height / 3
            }
        }
        Icon {
            name: "mail"

            Badge {
                x: parent.width - width / 2
                y: -height / 3
                count: 12
            }
        }
        Icon {
            name: "download"

            Badge {
                x: parent.width - width / 2
                y: -height / 3
                count: 1200
            }
        }
        Column {
            width: Metrics.textFieldMinWidth
            spacing: Theme.spacing.small ?? 0

            Divider {
                width: parent.width
            }
            Divider {
                width: parent.width
                inset: "start"
            }
            Divider {
                width: parent.width
                inset: "both"
            }
        }
    }

    Section {
        title: "Progreso"

        Column {
            width: Metrics.textFieldMinWidth * 1.5
            spacing: Theme.spacing.large ?? 0

            LinearProgress {
                width: parent.width
                value: 0.3
            }
            LinearProgress {
                width: parent.width
                value: 0.72
            }
            LinearProgress {
                width: parent.width
                indeterminate: true
            }
        }
        CircularProgress {
            value: 0.4
        }
        CircularProgress {
            indeterminate: true
        }
    }

    Section {
        title: "Formas expresivas"
        note: "ShapeEmblem con M3Shapes; pasa el ratón para transformarlas. Sin M3Shapes, un cuadrado redondeado."

        Repeater {
            model: [["cookie", "folder", "primaryContainer"], ["cookie12", "music_note", "tertiaryContainer"], ["flower", "photo", "secondaryContainer"], ["sunny", "star", "primaryContainer"], ["clover", "favorite", "tertiaryContainer"], ["squircle", "description", "secondaryContainer"], ["gem", "diamond", "primaryContainer"], ["burst", "bolt", "tertiaryContainer"]]

            ShapeEmblem {
                required property var modelData

                shape: modelData[0]
                icon: modelData[1]
                color: Theme["m3" + modelData[2]]
                iconColor: Theme["m3on" + modelData[2].charAt(0).toUpperCase() + modelData[2].slice(1)]
                morphOnHover: true
                hoverShape: "puffy"
            }
        }
    }
}
