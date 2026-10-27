// Inicio: the date and a greeting, a bento of hero tiles (now playing or keep listening, Tus me gusta, a mix,
// recent), then shelves: recently played, your playlists, your most played, albums and your artists.
import QtQuick
import WysunM3
import "../parts"

FocusScope {
    id: page

    property var app
    property string route
    readonly property string kind: "home"
    readonly property var home: music.home
    readonly property real scrollOffset: flick.contentY

    function act(tile) {
        if (tile.action === "mix")
            player.shuffleLibrary();
        else if (tile.action === "open")
            app.navigate("collection:" + tile.collection, true);
        else if (tile.action === "resume") {
            if (player.currentKey !== tile.key)
                player.play(tile.key, music.homeRecentModel.keys, tile.context);
            if (app.panel === "")
                app.togglePanel("now");
        }
    }

    EmptyState {
        anchors.fill: parent
        visible: page.home.empty === true
        emblemShape: "flower"
        icon: "library_music"
        title: "Tu biblioteca está vacía"
        message: "Añade una carpeta de música o busca canciones para descargar."
        actionText: "Añadir música"
        onAction: page.app.navigate("downloads", true)
    }

    Flickable {
        id: flick

        anchors.fill: parent
        visible: page.home.empty !== true
        contentHeight: column.implicitHeight + 2 * MusicMetrics.pagePadding
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: column

            x: MusicMetrics.pagePadding
            y: MusicMetrics.pagePadding
            width: flick.width - 2 * x
            spacing: Theme.spacing.extraLarge ?? 0

            Column {
                objectName: "greeting"
                width: parent.width

                Label {
                    role: "label.large"
                    text: (page.home.date ?? "").toUpperCase()
                    color: Theme.m3onSurfaceVariant
                }
                Label {
                    role: "headline.large"
                    text: page.home.greeting ?? ""
                }
                Label {
                    role: "body.medium"
                    text: page.home.summary ?? ""
                    color: Theme.m3onSurfaceVariant
                }
            }

            Flow {
                id: bento

                objectName: "bento"
                readonly property bool wide: width >= MusicMetrics.bentoWideFrom
                readonly property var tiles: (page.home.bento ?? []).filter(t => t.enabled !== false)
                // Wide: the resume tile takes half the row beside two quarter tiles, recent spans below. Narrow:
                // resume and recent span, the two small tiles share a row.
                readonly property real quarter: (width - 3 * spacing) / 4
                readonly property real half: (width - spacing) / 2

                width: parent.width
                spacing: Theme.spacing.medium ?? 0

                Repeater {
                    model: bento.tiles

                    BentoTile {
                        required property var modelData
                        readonly property bool resume: modelData.style === "resume"
                        readonly property bool spans: modelData.style === "wide"

                        width: spans ? bento.width : resume ? (bento.wide ? 2 * bento.quarter + bento.spacing : bento.width) : bento.wide ? bento.quarter : bento.half
                        eyebrow: modelData.eyebrow ?? ""
                        title: modelData.title ?? ""
                        subtitle: modelData.subtitle ?? ""
                        symbol: modelData.symbol ?? ""
                        shape: ({accent: "sunny", tonal: "clover", wide: "flower"})[modelData.style] ?? "cookie"
                        coverTile: resume && modelData.key !== ""
                        coverUrl: resume ? player.coverUrl || covers.url(modelData.key ?? "") : ""
                        spinning: resume && player.playing
                        tone: ({resume: Theme.m3primaryContainer, accent: Theme.m3tertiaryContainer, tonal: Theme.m3secondaryContainer})[modelData.style] ?? Theme.m3surfaceContainerHigh
                        onTone: ({resume: Theme.m3onPrimaryContainer, accent: Theme.m3onTertiaryContainer, tonal: Theme.m3onSecondaryContainer})[modelData.style] ?? Theme.m3onSurface
                        buttons: resume && modelData.key !== "" ? [{id: "play", text: player.playing ? "Pausar" : "Reproducir", icon: player.playing ? "pause" : "play_arrow", type: "filled"}, {id: "lyrics", text: "Letra", icon: "lyrics"}] : []
                        onOpened: page.act(modelData)
                        onButtonClicked: id => {
                            if (id === "lyrics")
                                page.app.togglePanel("lyrics");
                            else if (player.currentKey === modelData.key)
                                player.toggle();
                            else
                                player.play(modelData.key, music.homeRecentModel.keys, modelData.context);
                        }
                    }
                }
            }

            Shelf {
                objectName: "recentShelf"
                width: parent.width
                title: "Escuchado recientemente"
                showMore: music.homeRecentModel.count > 6
                onMore: page.app.navigate("collection:recent", true)
                model: music.homeRecentModel
                delegate: MusicCard {
                    entranceIndex: index
                    title: model.title
                    subtitle: model.artist
                    covers: model.cover ? [model.cover] : []
                    placeholderIcon: "music_note"
                    playing: model.playing
                    onOpened: player.play(model.key, music.homeRecentModel.keys, "recent")
                    onPlayRequested: player.playOrToggle(model.key, music.homeRecentModel.keys, "recent")
                    onContextRequested: (x, y) => page.app.menus.trackMenu([model.key], "", x, y)
                }
            }

            Shelf {
                width: parent.width
                title: "Tus playlists"
                note: "Listas que guardaste o creaste"
                model: music.homePlaylistsModel
                delegate: CollectionCard {
                    app: page.app
                }
            }

            Column {
                objectName: "chart"
                width: parent.width
                spacing: Theme.spacing.medium ?? 0
                visible: music.homeChartModel.count > 0

                Column {
                    Label {
                        role: "title.large"
                        text: "Lo que más escuchas"
                    }
                    Label {
                        role: "body.medium"
                        text: "Tus canciones más reproducidas"
                        color: Theme.m3onSurfaceVariant
                    }
                }

                Grid {
                    width: parent.width
                    columns: Math.max(1, Math.floor(width / MusicMetrics.chartRowWidth))
                    columnSpacing: Theme.spacing.large ?? 0

                    Repeater {
                        model: music.homeChartModel

                        ChartRow {
                            width: (parent.width - parent.columnSpacing * (parent.columns - 1)) / parent.columns
                            rank: model.number
                            title: model.title
                            artist: model.artist
                            coverUrl: model.cover
                            playing: model.current
                            onPlayRequested: player.playOrToggle(model.key, music.homeChartModel.keys, "top")
                        }
                    }
                }
            }

            Shelf {
                width: parent.width
                title: "Álbumes"
                showMore: music.homeAlbumsModel.count > 4
                onMore: page.app.navigate("library:albums", true)
                model: music.homeAlbumsModel
                delegate: CollectionCard {
                    app: page.app
                }
            }

            Shelf {
                width: parent.width
                title: "Tus artistas"
                showMore: true
                onMore: page.app.navigate("library:artists", true)
                model: music.homeArtistsModel
                delegate: CollectionCard {
                    app: page.app
                }
            }
        }
    }
}
