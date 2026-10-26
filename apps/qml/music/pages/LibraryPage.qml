// Biblioteca: Álbumes · Artistas · Canciones · Listas as tabs (route library:<tab>). Album and artist walls are
// adaptive grids; songs is the full TrackList with Todo / Recientes / Tus me gusta filters and a sort menu;
// lists starts with Tus me gusta and Recientes, then your playlists and the imported ones.
import QtQuick
import WysunM3
import "../parts"

FocusScope {
    id: page

    property var app
    property string route
    readonly property string kind: "library"
    readonly property string tab: route.split(":")[1] || "albums"
    readonly property real scrollOffset: 0
    property string songFilter: "all"
    property string songSort: "custom"
    readonly property var labels: ({albums: ["álbum", "álbumes"], artists: ["artista", "artistas"], songs: ["canción", "canciones"], lists: ["lista", "listas"]})
    readonly property int count: tab === "songs" ? songs.count : grid.count

    Column {
        id: head

        x: MusicMetrics.pagePadding
        y: Theme.padding.large ?? 0
        width: parent.width - 2 * x
        spacing: Theme.spacing.small ?? 0

        Row {
            spacing: Theme.spacing.medium ?? 0

            Label {
                role: "headline.medium"
                text: "Biblioteca"
            }
            Label {
                objectName: "libraryCount"
                anchors.baseline: parent.children[0].baseline
                role: "body.large"
                text: page.count + " " + page.labels[page.tab][page.count === 1 ? 0 : 1]
                color: Theme.m3onSurfaceVariant
            }
        }

        TabBar {
            objectName: "libraryTabs"
            width: Math.min(parent.width, Metrics.textFieldMinWidth * 3)
            tabs: [{id: "albums", text: "Álbumes", icon: "album"}, {id: "artists", text: "Artistas", icon: "artist"}, {id: "songs", text: "Canciones", icon: "music_note"}, {id: "lists", text: "Listas", icon: "queue_music"}]
            currentId: page.tab
            onActivated: id => page.app.navigate("library:" + id, true)
        }

        Item {
            visible: page.tab === "songs"
            width: parent.width
            height: visible ? Metrics.chipHeight + (Theme.spacing.small ?? 0) : 0

            Row {
                spacing: Theme.spacing.small ?? 0

                Repeater {
                    model: [{id: "all", text: "Todo"}, {id: "recent", text: "Recientes", icon: "history"}, {id: "favorites", text: "Tus me gusta", icon: "favorite"}]

                    Chip {
                        required property var modelData

                        kind: "filter"
                        text: modelData.text
                        icon: modelData.icon ?? ""
                        selected: page.songFilter === modelData.id
                        onClicked: page.songFilter = modelData.id
                    }
                }
            }

            Chip {
                id: sortChip

                anchors.right: parent.right
                kind: "assist"
                icon: "sort"
                text: ({custom: "Orden de la biblioteca", title: "Título", artist: "Artista", album: "Álbum", duration: "Duración"})[page.songSort]
                onClicked: {
                    const p = mapToItem(null, 0, height);
                    page.app.menus.sortMenu(page.songSort, s => page.songSort = s, p.x, p.y);
                }
            }
        }
    }

    // Songs: the library's keys, filtered and sorted on the Python side.
    readonly property var songKeys: {
        music.librarySongsModel.count;               // re-evaluate when the library changes
        return music.songs(songFilter, songSort);
    }
    TrackListModelProxy {
        id: songsModel

        keys: page.songKeys
    }

    TrackList {
        id: songs

        objectName: "songList"
        visible: page.tab === "songs"
        anchors.top: head.bottom
        anchors.topMargin: Theme.spacing.small ?? 0
        anchors.bottom: parent.bottom
        x: Theme.padding.large ?? 0
        width: parent.width - 2 * x
        model: songsModel.model
        contextId: page.songFilter === "all" ? "all" : page.songFilter
        onArtistRequested: name => page.app.navigate("collection:artist:" + name, true)
        onContextRequested: (keys, x, y) => page.app.menus.trackMenu(keys, "", x, y)
    }

    SelectionBar {
        visible: page.tab === "songs" && songs.selecting
        anchors.top: songs.top
        x: songs.x
        width: songs.width
        list: songs
        menus: page.app.menus
    }

    GridView {
        id: grid

        objectName: "libraryGrid"
        readonly property int columns: Math.max(2, Math.floor(width / (MusicMetrics.cardWidth + (Theme.spacing.large ?? 0))))

        visible: page.tab !== "songs"
        anchors.top: head.bottom
        anchors.topMargin: Theme.spacing.large ?? 0
        anchors.bottom: parent.bottom
        x: MusicMetrics.pagePadding
        width: parent.width - 2 * x
        cellWidth: width / columns
        cellHeight: cellWidth - (Theme.spacing.large ?? 0) + Metrics.listItemOneLine + (Theme.spacing.large ?? 0)
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: true
        activeFocusOnTab: true
        reuseItems: true
        model: page.tab === "artists" ? music.libraryArtistsModel : page.tab === "lists" ? music.libraryListsModel : music.libraryAlbumsModel
        delegate: Item {
            width: grid.cellWidth
            height: grid.cellHeight

            CollectionCard {
                width: grid.cellWidth - (Theme.spacing.large ?? 0)
                app: page.app
                focus: GridView.isCurrentItem
            }
        }
    }

    EmptyState {
        anchors.top: head.bottom
        anchors.bottom: parent.bottom
        width: parent.width
        visible: page.count === 0 && page.tab !== "lists"
        emblemShape: page.tab === "artists" ? "cookie" : "squircle"
        icon: page.tab === "artists" ? "artist" : page.tab === "songs" ? "music_note" : "album"
        title: "Todavía no hay nada aquí"
        message: page.songFilter === "favorites" && page.tab === "songs" ? "Marca canciones con el corazón para verlas aquí." : "Añade música desde «Añadir música»."
        actionText: "Añadir música"
        onAction: page.app.navigate("downloads", true)
    }
}
