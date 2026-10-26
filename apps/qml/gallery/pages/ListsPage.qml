// List items (one to three lines, leading/trailing variants), cards and a 10 000-row ListView (the scroll bench).
import QtQuick
import WysunM3
import ".."

Page {
    id: page

    benchView: big

    Section {
        title: "Elementos de lista"

        Column {
            width: Math.min(parent.width, Metrics.textFieldMinWidth * 2.4)

            ListItem {
                width: parent.width
                headline: "Documentos"
                leadingIcon: "folder"
                trailingText: "24"
                selected: true
            }
            ListItem {
                width: parent.width
                headline: "Informe final.pdf"
                supporting: "Modificado hoy · 2,4 MB"
                leadingIcon: "picture_as_pdf"
                trailing: Component {
                    IconButton {
                        icon: "more_vert"
                    }
                }
            }
            ListItem {
                width: parent.width
                lines: 3
                overline: "Álbum"
                headline: "Kind of Blue"
                supporting: "Miles Davis · 1959 · 5 canciones, 45 min de jazz modal"
                leadingAvatar: "KB"
                divider: true
            }
            ListItem {
                width: parent.width
                headline: "Elemento deshabilitado"
                leadingIcon: "block"
                disabled: true
            }
        }
    }

    Section {
        title: "Tarjetas"

        Repeater {
            model: ["elevated", "filled", "outlined"]

            Card {
                required property string modelData

                width: Metrics.textFieldMinWidth
                height: Metrics.topAppBarLarge
                variant: modelData
                clickable: true
                onClicked: page.snackbars?.show("Tarjeta " + modelData)

                Column {
                    spacing: Theme.spacing.small ?? 0

                    ShapeEmblem {
                        size: Metrics.listAvatarSize
                        shape: "cookie"
                        icon: "album"
                    }
                    Label {
                        role: "title.medium"
                        text: modelData
                    }
                    Label {
                        role: "body.medium"
                        text: "Tarjeta " + modelData
                        color: Theme.m3onSurfaceVariant
                    }
                }
            }
        }
    }

    Section {
        title: "10 000 elementos"
        note: "Solo se crean los delegados visibles."

        Rectangle {
            width: parent.width
            height: Metrics.listItemTwoLine * 6
            radius: Theme.rounding.large ?? 0
            color: Theme.m3surfaceContainerLow
            clip: true

            ListView {
                id: big

                objectName: "bigList"
                anchors.fill: parent
                model: 10000
                reuseItems: true
                delegate: ListItem {
                    required property int index

                    width: ListView.view.width
                    headline: "Elemento " + (index + 1)
                    supporting: "Fila " + (index + 1) + " de 10 000"
                    leadingIcon: index % 3 === 0 ? "description" : index % 3 === 1 ? "image" : "music_note"
                    trailingText: (index % 97) + " KB"
                }
            }
        }
    }
}
