// A titled group of settings: the title in the accent colour, then its rows one under the other.
import QtQuick
import WysunM3

Column {
    id: root

    property string title

    width: parent ? parent.width : implicitWidth

    Label {
        text: root.title
        role: "title.small"
        color: Theme.m3primary
        topPadding: Theme.padding.large ?? 0
        bottomPadding: Theme.padding.small ?? 0
        leftPadding: Theme.padding.medium ?? 0
    }
}
