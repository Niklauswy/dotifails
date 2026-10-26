// A titled horizontal shelf of cards (home): headline, optional note and «Ver todo»; the row scrolls
// sideways and ←/→ move between its cards.
import QtQuick
import WysunM3

Column {
    id: root

    property string title
    property string note
    property string moreText: "Ver todo"
    property bool showMore
    property alias model: row.model
    property alias delegate: row.delegate
    property real itemHeight: MusicMetrics.cardCover + Metrics.listItemOneLine
    property real itemWidth: MusicMetrics.cardWidth
    readonly property int count: row.count

    signal more

    spacing: Theme.spacing.medium ?? 0
    visible: row.count > 0

    Item {
        width: parent.width
        height: Math.max(heading.height, moreButton.height)

        Column {
            id: heading

            anchors.verticalCenter: parent.verticalCenter

            Label {
                role: "title.large"
                text: root.title
            }
            Label {
                visible: root.note !== ""
                role: "body.medium"
                text: root.note
                color: Theme.m3onSurfaceVariant
            }
        }

        Button {
            id: moreButton

            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: root.showMore
            type: "text"
            text: root.moreText
            onClicked: root.more()
        }
    }

    ListView {
        id: row

        width: parent.width
        height: root.itemHeight
        orientation: ListView.Horizontal
        spacing: Theme.spacing.large ?? 0
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: true
        activeFocusOnTab: false
        cacheBuffer: root.itemWidth * 2
    }
}
