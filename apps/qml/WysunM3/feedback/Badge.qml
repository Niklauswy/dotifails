// M3 badge: a 6 px dot for "something new", or a 16 px pill with a count (above Metrics.badgeMaxCount it reads
// "99+"). Anchor it to the top-end corner of an icon.
import QtQuick
import WysunM3

Rectangle {
    id: root

    property int count: 0
    readonly property string label: count > Metrics.badgeMaxCount ? Metrics.badgeMaxCount + "+" : count > 0 ? String(count) : ""

    implicitHeight: count > 0 ? Metrics.badgeLarge : Metrics.badgeSmall
    implicitWidth: count > 0 ? Math.max(Metrics.badgeLarge, text.implicitWidth + 2 * (Theme.padding.extraSmall ?? 0)) : Metrics.badgeSmall
    width: implicitWidth
    height: implicitHeight
    radius: Theme.fullRadius(height)
    color: Theme.m3error

    Label {
        id: text

        anchors.centerIn: parent
        visible: root.count > 0
        role: "label.small"
        text: root.label
        color: Theme.m3onError
    }
}
