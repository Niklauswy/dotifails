// «A continuación»: the song playing, then what comes next with where it comes from («De …»). Click jumps to a
// song; the menu plays it now, removes it, or opens the full song menu.
import QtQuick
import WysunM3
import "parts"

Flickable {
    id: root

    property var app
    property string note

    contentHeight: column.implicitHeight
    boundsBehavior: Flickable.StopAtBounds
    clip: true

    Column {
        id: column

        width: root.width
        spacing: Theme.spacing.small ?? 0

        Label {
            width: parent.width
            visible: root.note !== ""
            role: "body.medium"
            text: root.note
            color: Theme.m3onSurfaceVariant
            wrapMode: Text.Wrap
        }

        Label {
            role: "title.small"
            text: "Sonando ahora"
            color: Theme.m3onSurfaceVariant
        }

        TrackList {
            width: parent.width
            height: count * MusicMetrics.trackRow
            interactive: false
            numbered: true
            albums: false
            striped: false
            model: player.currentModel
            onContextRequested: (keys, x, y) => root.app.menus.trackMenu(keys, "", x, y)
        }

        Item {
            width: parent.width
            height: Metrics.buttonHeight
            visible: player.upcomingModel.count > 0

            Label {
                anchors.verticalCenter: parent.verticalCenter
                role: "title.small"
                text: "A continuación"
                color: Theme.m3onSurfaceVariant
            }
            Label {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                role: "body.small"
                text: player.contextTitle
                color: Theme.m3onSurfaceVariant
            }
        }

        TrackList {
            id: upcoming

            objectName: "upcomingList"
            width: parent.width
            height: count * MusicMetrics.trackRow
            interactive: false
            numbered: false
            albums: false
            striped: false
            model: player.upcomingModel
            // A click jumps to that song instead of starting a new context.
            playHandler: index => player.jumpTo(index)
            onContextRequested: (keys, x, y) => queueMenu.show(upcoming.currentIndex, keys, x, y)
        }

        EmptyState {
            width: parent.width
            height: MusicMetrics.heroCover * 1.5
            visible: player.upcomingModel.count === 0
            emblemShape: "puffy"
            icon: "queue_music"
            title: "No hay nada a continuación"
            message: "Añade canciones a la cola desde su menú."
        }
    }

    Menu {
        id: queueMenu

        property int index: -1
        property var keys: []
        property point at

        function show(i, k, x, y) {
            index = i;
            keys = k;
            at = Qt.point(x, y);
            popup(null, x, y);
        }

        objectName: "queueMenu"
        host: root.app.overlayHost
        model: [{id: "now", text: "Reproducir ahora", icon: "play_arrow"}, {id: "remove", text: "Quitar de la cola", icon: "remove_from_queue"}, {divider: true}, {id: "more", text: "Más opciones…", icon: "more_horiz"}]
        onTriggered: id => {
            if (id === "now")
                player.jumpTo(index);
            else if (id === "remove")
                player.removeUpcoming(index);
            else
                root.app.menus.trackMenu(keys, "", at.x, at.y);
        }
    }
}
