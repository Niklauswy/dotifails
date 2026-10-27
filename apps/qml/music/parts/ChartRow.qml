// One row of «Lo que más escuchas»: rank, cover, title and artist; clicking plays it.
import QtQuick
import WysunM3

Item {
    id: root

    property int rank
    property string title
    property string artist
    property url coverUrl
    property bool playing

    signal playRequested

    implicitWidth: MusicMetrics.chartRowWidth
    implicitHeight: Metrics.listItemOneLine
    activeFocusOnTab: true
    Keys.onReturnPressed: playRequested()

    Row {
        anchors.fill: parent
        anchors.leftMargin: Theme.padding.small ?? 0
        spacing: Theme.spacing.medium ?? 0

        Label {
            anchors.verticalCenter: parent.verticalCenter
            width: Metrics.iconSize
            role: "headline.small"
            text: root.rank
            color: root.playing ? Theme.m3primary : Theme.m3onSurfaceVariant
            horizontalAlignment: Text.AlignHCenter
        }
        Cover {
            anchors.verticalCenter: parent.verticalCenter
            width: MusicMetrics.trackCover
            height: width
            source: root.coverUrl
            shape: "squircle"
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - x

            Label {
                width: parent.width
                role: "title.small"
                text: root.title
                color: root.playing ? Theme.m3primary : Theme.m3onSurface
                elide: Text.ElideRight
            }
            Label {
                width: parent.width
                role: "body.small"
                text: root.artist
                color: Theme.m3onSurfaceVariant
                elide: Text.ElideRight
            }
        }
    }

    StateLayer {
        radius: Theme.rounding.medium ?? 0
        focused: root.activeFocus
        onClicked: root.playRequested()
    }
}
