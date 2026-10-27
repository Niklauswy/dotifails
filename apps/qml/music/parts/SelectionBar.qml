// The contextual bar of a multiple selection: count, play next, add to the queue, add to a playlist,
// favourite, and clear. It floats over the top of the list it belongs to.
import QtQuick
import WysunM3

Surface {
    id: root

    property var list
    property var menus
    readonly property var keys: list ? list.selectedKeys : []

    objectName: "selectionBar"
    visible: keys.length > 0
    implicitHeight: Metrics.topAppBarSmall
    radius: Theme.rounding.extraLarge ?? 0
    container: Theme.m3secondaryContainer
    color: container
    level: 2

    Row {
        anchors.fill: parent
        anchors.leftMargin: Theme.padding.small ?? 0
        anchors.rightMargin: Theme.padding.small ?? 0
        spacing: Theme.spacing.small ?? 0

        IconButton {
            anchors.verticalCenter: parent.verticalCenter
            icon: "close"
            onClicked: root.list.clearSelection()

            Tooltip {
                text: "Quitar la selección · Esc"
            }
        }
        Label {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - x - actions.width - parent.spacing
            role: "title.medium"
            text: root.keys.length === 1 ? "1 canción seleccionada" : root.keys.length + " canciones seleccionadas"
            color: Theme.m3onSecondaryContainer
            elide: Text.ElideRight
        }
        Row {
            id: actions

            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacing.extraSmall ?? 0

            IconButton {
                icon: "playlist_play"
                onClicked: player.playNext(root.keys)

                Tooltip {
                    text: "Reproducir a continuación"
                }
            }
            IconButton {
                icon: "add_to_queue"
                onClicked: player.addToQueue(root.keys)

                Tooltip {
                    text: "Añadir a la cola"
                }
            }
            IconButton {
                id: toPlaylist

                icon: "playlist_add"
                onClicked: {
                    const p = mapToItem(null, 0, height);
                    root.menus.playlistMenu(root.keys, p.x, p.y);
                }

                Tooltip {
                    text: "Añadir a playlist"
                }
            }
            IconButton {
                readonly property bool all: music.allFavorite(root.keys)

                icon: "favorite"
                checkable: true
                checked: all
                onClicked: music.setFavorite(root.keys, !all)

                Tooltip {
                    text: "Tus me gusta"
                }
            }
        }
    }
}
