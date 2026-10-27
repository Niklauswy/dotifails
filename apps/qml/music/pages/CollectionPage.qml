// A collection: album, playlist, artist, Tus me gusta, Recientes or «Ver todas» of a search. The header shows the
// artwork in a shape of its kind (album squircle, artist cookie with the photo or initials, Tus me gusta sunny,
// Recientes burst) over a wash of its colour; it scrolls away into a compact bar. Then play / shuffle / more,
// the in-list filter and the sort, the artist's albums, and the songs.
import QtQuick
import QtQuick.Effects
import WysunM3
import "../parts"

FocusScope {
    id: page

    property var app
    property string collectionId
    readonly property string kind: "collection"
    // The shared collection data belongs to the page that opened it last: a page that is leaving (shared axis)
    // keeps its own header and lets go of the song list instead of showing the next collection's.
    readonly property bool owner: music.collection.id === collectionId
    property var info: ({})
    readonly property bool exists: info.exists === true && info.id === collectionId
    Binding on info {
        when: page.owner
        value: music.collection
        restoreMode: Binding.RestoreNone
    }
    readonly property bool isPlaying: player.playing && player.contextId === collectionId
    readonly property var coverList: {
        covers.revision;
        return collectionId === "" ? [] : covers.collection(collectionId);
    }
    readonly property real scrollOffset: list.contentY - list.originY
    readonly property bool compact: scrollOffset > MusicMetrics.heroCover * 0.6

    Component.onCompleted: music.openCollection(collectionId)
    onCollectionIdChanged: music.openCollection(collectionId)

    EmptyState {
        objectName: "orphanState"
        anchors.fill: parent
        visible: !page.exists
        emblemShape: "clover"
        icon: "playlist_remove"
        title: "Esta lista ya no existe."
        message: "Se borró o se renombró. Vuelve a tu biblioteca."
        actionText: "Ir a Inicio"
        onAction: page.app.navigate("home", true)
    }

    readonly property string tone: {
        covers.revision;
        return page.exists ? music.toneOf(collectionId) : "";
    }

    // The artwork as the page's atmosphere: blurred behind the header, sliding slower than the list (parallax) and
    // fading as it scrolls away.
    AmbientBackdrop {
        visible: page.exists
        width: parent.width
        height: MusicMetrics.heroCover * 2.6
        y: -Math.min(page.scrollOffset, height) * 0.45
        opacity: Math.max(0, 1 - page.scrollOffset / height)
        source: page.coverList.length > 0 ? page.coverList[0] : ""
        tone: page.tone !== "" ? page.tone : page.info.kind === "favorites" ? Theme.m3tertiaryContainer : Theme.m3secondaryContainer
    }

    TrackList {
        id: list

        objectName: "collectionTracks"
        visible: page.exists
        anchors.fill: parent
        anchors.leftMargin: Theme.padding.large ?? 0
        anchors.rightMargin: Theme.padding.large ?? 0
        model: page.owner ? music.collectionTracksModel : null
        contextId: page.collectionId
        covers: page.info.kind !== "album"
        albums: page.info.kind !== "album" && width >= Metrics.windowMedium
        onArtistRequested: name => page.app.navigate("collection:artist:" + name, true)
        onContextRequested: (keys, x, y) => page.app.menus.trackMenu(keys, page.collectionId, x, y)
        // The header settles its height after the artwork and the title are laid out; until the user scrolls,
        // keep the view at its top (a ListView keeps its first row still, so a growing header slid upwards).
        property bool userScrolled
        onMovementStarted: userScrolled = true
        onOriginYChanged: {
            if (!userScrolled)
                contentY = originY;
        }
        header: Column {
            onHeightChanged: {
                if (!list.userScrolled)
                    Qt.callLater(list.positionViewAtBeginning);
            }
            width: list.width
            spacing: Theme.spacing.large ?? 0
            topPadding: Theme.padding.large ?? 0
            bottomPadding: Theme.padding.small ?? 0

            Row {
                objectName: "collectionHero"
                width: parent.width
                spacing: Theme.spacing.extraLarge ?? 0

                Item {
                    id: heroCover

                    objectName: "heroCoverBox"
                    readonly property real tiltX: hover.hovered ? (hover.point.position.y / height - 0.5) * -12 : 0
                    readonly property real tiltY: hover.hovered ? (hover.point.position.x / width - 0.5) * 12 : 0

                    width: Math.min(MusicMetrics.heroCover * 1.15, list.width * 0.38)
                    height: width

                    HoverHandler {
                        id: hover
                    }

                    RectangularShadow {
                        anchors.fill: cover
                        visible: page.info.kind === "album" || page.info.kind === "user" || page.info.kind === "playlist" || page.info.kind === "ranking"
                        radius: Theme.rounding.extraLarge ?? 0
                        blur: 36
                        offset.y: 14
                        color: Qt.alpha(Theme.m3shadow, 0.5)
                    }

                    Cover {
                        id: cover

                        objectName: "heroCover"
                        anchors.fill: parent
                        sources: page.coverList
                        initials: page.info.initials ?? ""
                        shape: ({album: "squircle", artist: "cookie", favorites: "sunny", recent: "burst", user: "squircle"})[page.info.kind] ?? "squircle"
                        placeholderIcon: ({artist: "person", favorites: "favorite", recent: "history", album: "album"})[page.info.kind] ?? "queue_music"
                        fill: page.info.kind === "favorites" ? Theme.m3tertiaryContainer : page.info.kind === "recent" ? Theme.m3primaryContainer : Theme.m3secondaryContainer
                        placeholderColor: page.info.kind === "favorites" ? Theme.m3onTertiaryContainer : page.info.kind === "recent" ? Theme.m3onPrimaryContainer : Theme.m3onSecondaryContainer
                        spinning: page.isPlaying && page.info.kind !== "album"
                        scale: hover.hovered ? 1.03 : 1
                        transform: [
                            Rotation {
                                origin.x: cover.width / 2
                                origin.y: cover.height / 2
                                axis {
                                    x: 1
                                    y: 0
                                    z: 0
                                }
                                angle: heroCover.tiltX

                                SpringBehavior on angle {
                                    kind: "fastSpatial"
                                }
                            },
                            Rotation {
                                origin.x: cover.width / 2
                                origin.y: cover.height / 2
                                axis {
                                    x: 0
                                    y: 1
                                    z: 0
                                }
                                angle: heroCover.tiltY

                                SpringBehavior on angle {
                                    kind: "fastSpatial"
                                }
                            }
                        ]

                        SpringBehavior on scale {
                            kind: "defaultSpatial"
                        }
                    }
                }

                Column {
                    anchors.bottom: heroCover.bottom
                    width: parent.width - heroCover.width - parent.spacing
                    spacing: Theme.spacing.extraSmall ?? 0

                    Label {
                        role: "label.large"
                        text: (page.info.label ?? "").toUpperCase()
                        color: Theme.m3onSurfaceVariant
                    }
                    Label {
                        objectName: "collectionTitle"
                        width: parent.width
                        role: "headline.large"
                        font.pointSize: Theme.typeFont("headline.large").pointSize * (list.width >= Metrics.windowMedium ? 1.6 : 1)
                        text: page.info.title ?? ""
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                    Label {
                        id: byline

                        width: Math.min(implicitWidth, parent.width)
                        visible: text !== ""
                        role: "title.medium"
                        text: page.info.byline ?? ""
                        color: Theme.m3primary
                        font.underline: bylineArea.containsMouse && page.info.kind === "album"

                        MouseArea {
                            id: bylineArea

                            anchors.fill: parent
                            enabled: page.info.kind === "album" && byline.text !== "Varios artistas"
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: page.app.navigate("collection:artist:" + byline.text, true)
                        }
                    }
                    Label {
                        role: "body.medium"
                        text: page.info.meta ?? ""
                        color: Theme.m3onSurfaceVariant
                    }
                }
            }

            Item {
                width: parent.width
                height: Metrics.fabRegular + (Theme.spacing.small ?? 0)

                Row {
                    spacing: Theme.spacing.small ?? 0

                    Fab {
                        objectName: "collectionPlay"
                        anchors.verticalCenter: parent.verticalCenter
                        extended: list.width >= Metrics.windowMedium
                        icon: page.isPlaying ? "pause" : "play_arrow"
                        text: page.isPlaying ? "Pausar" : "Reproducir"
                        // The album's own colour (artwork-derived tone over the primary container).
                        containerColor: page.tone !== "" ? Qt.tint(Theme.m3primaryContainer, Qt.alpha(page.tone, 0.55)) : Theme.m3primaryContainer
                        disabled: (page.info.count ?? 0) === 0
                        onClicked: player.toggleCollection(page.collectionId)
                    }
                    Button {
                        objectName: "collectionShuffle"
                        anchors.verticalCenter: parent.verticalCenter
                        type: "tonal"
                        text: "Aleatorio"
                        icon: "shuffle"
                        disabled: (page.info.count ?? 0) === 0
                        onClicked: player.playCollection(page.collectionId, "", true)
                    }
                    IconButton {
                        id: more

                        objectName: "collectionMore"
                        anchors.verticalCenter: parent.verticalCenter
                        type: "tonal"
                        icon: "more_horiz"
                        onClicked: {
                            const p = mapToItem(null, 0, height);
                            page.app.menus.collectionMenu(page.collectionId, null, p.x, p.y);
                        }

                        Tooltip {
                            text: "Más opciones"
                        }
                    }
                }

                Row {
                    anchors.right: parent.right
                    spacing: Theme.spacing.small ?? 0

                    TextField {
                        objectName: "collectionFilter"
                        visible: page.info.filterable === true
                        width: Metrics.textFieldMinWidth
                        variant: "filled"
                        label: "Buscar en la lista"
                        leadingIcon: "filter_list"
                        onTextChanged: music.setFilter(text)
                    }
                    IconButton {
                        objectName: "collectionSort"
                        anchors.verticalCenter: parent.verticalCenter
                        icon: "sort"
                        onClicked: {
                            const p = mapToItem(null, 0, height);
                            page.app.menus.sortMenu(page.info.sort ?? "custom", s => music.setSort(s), p.x, p.y);
                        }

                        Tooltip {
                            text: "Ordenar"
                        }
                    }
                }
            }

            Shelf {
                width: parent.width
                visible: page.info.kind === "artist" && count > 0
                title: "Álbumes"
                model: page.info.kind === "artist" ? music.artistAlbumsModel : null
                delegate: CollectionCard {
                    app: page.app
                }
            }

            Label {
                visible: page.info.kind === "artist"
                role: "title.large"
                text: "Canciones"
            }
        }
    }

    // The compact header once the big one has scrolled away.
    Surface {
        objectName: "compactHeader"
        visible: page.exists
        width: parent.width
        height: Metrics.topAppBarSmall
        container: Theme.m3surfaceContainer
        color: container
        opacity: page.compact ? 1 : 0
        enabled: page.compact

        SpringBehavior on opacity {
            kind: "fastEffects"
        }

        Row {
            anchors.fill: parent
            anchors.leftMargin: Theme.padding.large ?? 0
            spacing: Theme.spacing.medium ?? 0

            Cover {
                anchors.verticalCenter: parent.verticalCenter
                width: MusicMetrics.trackCover
                height: width
                sources: page.coverList
                shape: heroShape()
                function heroShape() {
                    return ({artist: "cookie", favorites: "sunny", recent: "burst"})[page.info.kind] ?? "squircle";
                }
            }
            Label {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - x - compactPlay.width - 2 * parent.spacing
                role: "title.large"
                text: page.info.title ?? ""
                elide: Text.ElideRight
            }
            IconButton {
                id: compactPlay

                anchors.verticalCenter: parent.verticalCenter
                type: "filled"
                icon: page.isPlaying ? "pause" : "play_arrow"
                onClicked: player.toggleCollection(page.collectionId)
            }
        }
    }

    SelectionBar {
        anchors.top: parent.top
        anchors.topMargin: Theme.spacing.small ?? 0
        x: list.x
        width: list.width
        list: list
        menus: page.app.menus
        z: 2
    }
}
