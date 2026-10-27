// Búsqueda (route search[:text]): with an empty query, Explorar — your lists, albums and most played artists
// as full-bleed tiles; while typing (rendered 140 ms after the last key), the top result (artist or song),
// five songs with «Ver las N canciones», artists, and playlists and albums. ↓/Enter in the search bar land on
// the songs; Enter plays among every match.
import QtQuick
import QtQuick.Effects
import WysunM3
import "../parts"

FocusScope {
    id: page

    property var app
    property string route
    readonly property string kind: "search"
    readonly property string query: route.indexOf(":") >= 0 ? route.slice(route.indexOf(":") + 1) : ""
    readonly property var result: music.search
    readonly property bool searching: result.searching === true
    readonly property real scrollOffset: flick.contentY

    onQueryChanged: debounce.restart()
    Component.onCompleted: music.setQuery(query)

    Timer {
        id: debounce

        interval: Theme.duration("small") * 0.7
        onTriggered: music.setQuery(page.query)
    }

    Flickable {
        id: flick

        anchors.fill: parent
        contentHeight: column.implicitHeight + 2 * MusicMetrics.pagePadding
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: column

            x: MusicMetrics.pagePadding
            y: Theme.padding.large ?? 0
            width: flick.width - 2 * x
            spacing: Theme.spacing.extraLarge ?? 0

            // ------------------------------------------------------- explore
            Column {
                objectName: "explore"
                visible: !page.searching
                width: parent.width
                spacing: Theme.spacing.large ?? 0

                Column {
                    Label {
                        role: "headline.medium"
                        text: "Explorar"
                    }
                    Label {
                        role: "body.medium"
                        text: "Tus listas, álbumes y artistas más escuchados"
                        color: Theme.m3onSurfaceVariant
                    }
                }

                Grid {
                    width: parent.width
                    columns: Math.max(2, Math.floor(width / (MusicMetrics.cardWidth * 1.4)))
                    spacing: Theme.spacing.medium ?? 0

                    Repeater {
                        model: music.exploreModel

                        ExploreTile {
                            width: (parent.width - parent.spacing * (parent.columns - 1)) / parent.columns
                            app: page.app
                        }
                    }
                }
            }

            // ------------------------------------------------------- results
            Row {
                visible: page.searching && !page.result.empty
                width: parent.width
                spacing: Theme.spacing.extraLarge ?? 0

                Column {
                    width: parent.width * 0.38
                    spacing: Theme.spacing.medium ?? 0
                    visible: page.result.top !== undefined && page.result.top.kind !== undefined

                    Label {
                        role: "title.large"
                        text: "Resultado principal"
                    }

                    Surface {
                        id: top

                        objectName: "topResult"
                        readonly property var info: page.result.top ?? {}
                        readonly property bool artist: info.kind === "artist"

                        width: parent.width
                        height: MusicMetrics.cardCover + Metrics.topAppBarSmall + Metrics.chipHeight
                        radius: Theme.rounding.extraLarge ?? 0
                        container: Theme.m3surfaceContainerHigh
                        color: container
                        activeFocusOnTab: true
                        Keys.onReturnPressed: topArea.clicked(null)

                        StateLayer {
                            id: topArea

                            radius: top.radius
                            focused: top.activeFocus
                            onClicked: {
                                if (top.artist)
                                    page.app.navigate("collection:" + top.info.id, true);
                                else
                                    player.play(top.info.key, music.searchKeys(page.query), "search:" + page.query);
                            }
                        }

                        Cover {
                            x: Theme.padding.large ?? 0
                            y: Theme.padding.large ?? 0
                            width: MusicMetrics.cardCover * 0.6
                            height: width
                            source: {
                                covers.revision;
                                return top.artist ? covers.url(top.info.id ?? "") : covers.url(top.info.key ?? "");
                            }
                            shape: top.artist ? "cookie" : "squircle"
                            initials: top.artist ? (top.info.title ?? "").split(" ").slice(0, 2).map(w => w.charAt(0)).join("").toUpperCase() : ""
                            placeholderIcon: top.artist ? "person" : "music_note"
                            fill: top.artist ? Theme.m3tertiaryContainer : Theme.m3surfaceContainerHighest
                            placeholderColor: top.artist ? Theme.m3onTertiaryContainer : Theme.m3onSurfaceVariant
                        }
                        Column {
                            x: Theme.padding.large ?? 0
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: Theme.padding.large ?? 0
                            width: parent.width - 2 * x - playTop.width
                            spacing: Theme.spacing.small ?? 0

                            Label {
                                width: parent.width
                                role: "headline.small"
                                text: top.info.title ?? ""
                                elide: Text.ElideRight
                            }
                            Chip {
                                kind: "suggestion"
                                text: top.info.subtitle ?? ""
                                enabled: false
                            }
                        }
                        Fab {
                            id: playTop

                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: Theme.padding.large ?? 0
                            icon: "play_arrow"
                            onClicked: {
                                if (top.artist)
                                    player.toggleCollection(top.info.id);
                                else
                                    player.play(top.info.key, music.searchKeys(page.query), "search:" + page.query);
                            }
                        }
                    }
                }

                Column {
                    width: parent.width - parent.children[0].width - parent.spacing
                    spacing: Theme.spacing.small ?? 0
                    visible: songs.count > 0

                    Item {
                        width: parent.width
                        height: Metrics.buttonHeight

                        Label {
                            anchors.verticalCenter: parent.verticalCenter
                            role: "title.large"
                            text: "Canciones"
                        }
                        Button {
                            objectName: "allSongs"
                            anchors.right: parent.right
                            visible: (page.result.songCount ?? 0) > songs.count
                            type: "text"
                            text: page.result.allSongs ?? ""
                            onClicked: page.app.navigate("collection:search:" + page.query, true)
                        }
                    }

                    TrackList {
                        id: songs

                        objectName: "searchSongs"
                        focus: true
                        width: parent.width
                        height: count * MusicMetrics.trackRow
                        interactive: false
                        numbered: false
                        albums: false
                        striped: false
                        model: music.searchSongsModel
                        contextKeys: music.searchKeys(page.query)
                        contextId: "search:" + page.query
                        onArtistRequested: name => page.app.navigate("collection:artist:" + name, true)
                        onContextRequested: (keys, x, y) => page.app.menus.trackMenu(keys, "", x, y)
                        onActiveFocusChanged: {
                            if (activeFocus && currentIndex < 0 && count > 0)
                                currentIndex = 0;
                        }
                    }
                }
            }

            Shelf {
                visible: page.searching && count > 0
                width: parent.width
                title: "Artistas"
                model: music.searchArtistsModel
                delegate: CollectionCard {
                    app: page.app
                }
            }

            Shelf {
                visible: page.searching && count > 0
                width: parent.width
                title: "Playlists y álbumes"
                model: music.searchListsModel
                delegate: CollectionCard {
                    app: page.app
                }
            }
        }
    }

    EmptyState {
        objectName: "noResults"
        anchors.fill: parent
        visible: page.searching && page.result.empty === true
        emblemShape: "sunny"
        icon: "search_off"
        title: "Sin resultados"
        message: page.result.emptyText ?? ""
        actionText: "Buscar en «Añadir música»"
        onAction: page.app.navigate("downloads", true)
    }
}
