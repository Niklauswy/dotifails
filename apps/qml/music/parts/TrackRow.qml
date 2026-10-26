// One song of a TrackList: number (or the playing bars, or a selection check), cover, title, artist (link),
// album, favourite, duration and «más». The current song shows in primary; a selected row in secondaryContainer.
import QtQuick
import WysunM3

Rectangle {
    id: root

    required property int index
    required property string key
    required property string title
    required property string artist
    required property var artists
    required property string album
    required property string durationText
    required property bool favorite
    required property string cover
    required property bool current
    required property bool playing
    required property int number

    property var list
    readonly property bool selected: list.selection[key] === true
    readonly property bool narrow: width < Metrics.windowMedium * 0.9
    readonly property color text: selected ? Theme.m3onSecondaryContainer : current ? Theme.m3primary : Theme.m3onSurface
    // Columns share what the number, cover and the trailing controls leave: title / artist / album.
    readonly property real _gap: Theme.spacing.medium ?? 0
    readonly property real _lead: (list.numbered || list.selecting ? Metrics.iconSize + (Theme.spacing.small ?? 0) + _gap : 0) + (list.covers ? MusicMetrics.trackCover + _gap : 0)
    readonly property real _flex: Math.max(0, width - (Theme.padding.medium ?? 0) - (Theme.padding.small ?? 0) - _lead - tail.width - _gap * (narrow ? 1 : list.albums ? 3 : 2))
    readonly property real titleWidth: narrow ? _flex : _flex * (list.albums ? 0.4 : 0.55)
    readonly property real artistWidth: narrow ? 0 : _flex * (list.albums ? 0.3 : 0.45)
    readonly property color muted: selected ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant

    objectName: "track-" + title
    width: ListView.view ? ListView.view.width : 0
    height: MusicMetrics.trackRow
    radius: Theme.rounding.medium ?? 0
    color: selected ? Theme.m3secondaryContainer : list.striped && index % 2 ? Qt.alpha(Theme.m3onSurface, Metrics.disabledOutline / 4) : "transparent"

    StateLayer {
        id: layer

        radius: root.radius
        ripple: false
        tint: root.text
        focused: root.ListView.isCurrentItem && root.list.activeFocus
        mouseArea.acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => root.list.rowClicked(root.index, mouse)
        onPressAndHold: root.list.toggleSelected(root.index)
        mouseArea.onDoubleClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                root.list.play(root.index);
        }
    }

    Row {
        anchors.fill: parent
        anchors.leftMargin: Theme.padding.medium ?? 0
        anchors.rightMargin: Theme.padding.small ?? 0
        spacing: root._gap

        Item {
            anchors.verticalCenter: parent.verticalCenter
            width: Metrics.iconSize + (Theme.spacing.small ?? 0)
            height: Metrics.iconSize
            visible: root.list.numbered || root.list.selecting

            Label {
                anchors.centerIn: parent
                visible: !root.current && !root.list.selecting
                role: "body.medium"
                text: root.number
                color: root.muted
            }
            EqBars {
                anchors.centerIn: parent
                visible: root.current && !root.list.selecting
                running: root.playing
                color: root.text
            }
            Icon {
                anchors.centerIn: parent
                visible: root.list.selecting
                name: root.selected ? "check_box" : "check_box_outline_blank"
                filled: root.selected
                color: root.text
            }
        }

        Cover {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.list.covers
            width: MusicMetrics.trackCover
            height: width
            source: root.cover
            shape: "squircle"
        }

        Label {
            anchors.verticalCenter: parent.verticalCenter
            width: root.titleWidth
            role: "body.large"
            text: root.title
            color: root.text
            elide: Text.ElideRight
        }

        Label {
            id: artistLabel

            anchors.verticalCenter: parent.verticalCenter
            visible: !root.narrow
            width: root.artistWidth
            role: "body.medium"
            text: root.artist
            color: artistArea.containsMouse ? Theme.m3primary : root.muted
            font.underline: artistArea.containsMouse
            elide: Text.ElideRight

            MouseArea {
                id: artistArea

                width: Math.min(parent.implicitWidth, parent.width)
                height: parent.height
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.list.artistRequested(root.artists[0] ?? "")
            }
        }

        Label {
            anchors.verticalCenter: parent.verticalCenter
            visible: !root.narrow && root.list.albums
            width: root.artistWidth
            role: "body.medium"
            text: root.album
            color: root.muted
            elide: Text.ElideRight
        }
    }

    Row {
        id: tail

        anchors.right: parent.right
        anchors.rightMargin: Theme.padding.small ?? 0
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.spacing.extraSmall ?? 0

        IconButton {
            objectName: "heart"
            anchors.verticalCenter: parent.verticalCenter
            checkable: true
            checked: root.favorite
            icon: "favorite"
            iconChecked: "favorite"
            opacity: root.favorite || layer.hovered || root.ListView.isCurrentItem ? 1 : 0
            onClicked: music.toggleFavorite(root.key)
        }
        Label {
            anchors.verticalCenter: parent.verticalCenter
            width: Metrics.listAvatarSize
            role: "body.medium"
            text: root.durationText
            color: root.muted
            horizontalAlignment: Text.AlignRight
        }
        IconButton {
            objectName: "more"
            anchors.verticalCenter: parent.verticalCenter
            icon: "more_vert"
            onClicked: {
                const p = mapToItem(null, 0, height);
                root.list.menuFor(root.index, p.x, p.y);
            }
        }
    }
}
