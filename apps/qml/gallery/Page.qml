// A scrolling gallery page. Pages get the gallery's snackbar host and overlay layer.
import QtQuick
import WysunM3

Flickable {
    id: root

    property Item snackbars
    property Item overlay
    property real windowWidth
    property Item benchView: null
    readonly property real scrollOffset: contentY
    default property alias sections: column.data

    contentHeight: column.implicitHeight + 2 * (Theme.padding.large ?? 0)
    boundsBehavior: Flickable.StopAtBounds
    clip: true

    Column {
        id: column

        x: Theme.padding.extraLarge ?? 0
        y: Theme.padding.large ?? 0
        width: root.width - 2 * x
        spacing: Theme.spacing.extraLarge ?? 0
    }
}
