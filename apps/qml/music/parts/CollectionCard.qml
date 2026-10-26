// A MusicCard for a row of a CardListModel (album, playlist, artist, Tus me gusta, Recientes): opens the
// collection, plays it from the card, and opens its menu on right click.
import QtQuick
import WysunM3

MusicCard {
    id: card

    // A Shelf or GridView delegate: the row's roles come in `model` (id, title, subtitle, kind, covers, round, playing).
    property var app
    readonly property string collectionId: model.id
    readonly property string kind: model.kind

    objectName: "card-" + collectionId
    title: model.title
    subtitle: model.subtitle
    covers: model.covers
    round: model.round
    playing: model.playing
    initials: round ? title.split(" ").slice(0, 2).map(w => w.charAt(0)).join("").toUpperCase() : ""
    shape: kind === "favorites" ? "sunny" : kind === "recent" ? "burst" : round ? "cookie" : "squircle"
    placeholderIcon: kind === "favorites" ? "favorite" : kind === "recent" ? "history" : round ? "person" : kind === "album" ? "album" : "queue_music"
    onOpened: app.navigate("collection:" + collectionId, true)
    onPlayRequested: player.toggleCollection(collectionId)
    onContextRequested: (x, y) => app.menus.collectionMenu(collectionId, null, x, y)
}
