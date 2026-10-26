// A collection (album, playlist, artist, favourites, recent, search results) of Wysun Music.
import QtQuick
import WysunM3

FocusScope {
    property var app
    property string collectionId
    readonly property string kind: "collection"
    readonly property bool exists: music.routeExists("collection:" + collectionId)
    property real scrollOffset: 0

    EmptyState {
        objectName: "orphanState"
        anchors.fill: parent
        visible: !parent.exists
        emblemShape: "clover"
        icon: "playlist_remove"
        title: "Esta lista ya no existe."
        message: "Se borró o se renombró. Vuelve a tu biblioteca."
        actionText: "Ir a Inicio"
        onAction: parent.app.navigate("home")
    }
}
