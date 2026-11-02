// An audio file: its cover art (or a note) in a cookie that turns slowly while it plays, the title and
// artist · album, above the control bar. The artwork component is Wysun Music's own Cover.
import QtQuick
import WysunM3
import "../music/parts" as MusicParts

Item {
    id: root

    property url cover
    property string title
    property string detail
    property bool playing
    property real reserve                 // room the control bar takes at the bottom

    Column {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -root.reserve / 2
        spacing: Theme.spacing.large ?? 0
        width: Math.min(root.width - 2 * (Theme.padding.extraLarge ?? 0), Metrics.textFieldMinWidth * 2)

        MusicParts.Cover {
            objectName: "audioCover"
            anchors.horizontalCenter: parent.horizontalCenter
            readonly property real side: Math.max(Metrics.emblemSize, Math.min(root.height - root.reserve - titleLabel.height * 3, root.width * 0.6, Metrics.textFieldMinWidth * 1.4))
            width: side
            height: side
            source: root.cover
            shape: "cookie"
            spinning: root.playing
            shadow: Theme.spacing.large ?? 0
            placeholderIcon: "music_note"
        }
        Label {
            id: titleLabel

            objectName: "audioTitle"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            role: "title.large"
            text: root.title
            elide: Text.ElideRight
        }
        Label {
            objectName: "audioDetail"
            width: parent.width
            visible: text !== ""
            horizontalAlignment: Text.AlignHCenter
            role: "body.medium"
            color: Theme.m3onSurfaceVariant
            text: root.detail
            elide: Text.ElideRight
        }
    }
}
