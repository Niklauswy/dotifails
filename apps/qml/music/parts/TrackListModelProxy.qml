// Gives a page its own TrackListModel (from music.newTrackList()) fed with `keys`.
import QtQuick

QtObject {
    id: root

    property var keys: []
    readonly property var model: music.newTrackList()

    onKeysChanged: model.setKeys(keys)
    Component.onCompleted: model.setKeys(keys)
    Component.onDestruction: music.releaseTrackList(model)
}
