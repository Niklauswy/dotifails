// The M3 snackbar surface (SnackbarHost shows and queues them): inverseSurface, extraSmall corner, 48 high or 68
// with two lines, body-medium text, an optional inversePrimary text action and close button.
import QtQuick
import WysunM3

Surface {
    id: root

    property string text
    property string actionText
    property bool closable
    property real maxWidth: Metrics.snackbarMaxWidth
    readonly property bool twoLines: label.lineCount > 1

    signal action
    signal closeRequested

    objectName: "snackbar"
    width: Math.min(maxWidth, implicitWidth)
    implicitWidth: label.implicitWidth + 2 * (Theme.padding.large ?? 0) + (actionButton.visible ? actionButton.width + (Theme.spacing.small ?? 0) : 0) + (closeButton.visible ? closeButton.width : 0)
    height: twoLines ? Metrics.snackbarTwoLineHeight : Metrics.snackbarHeight
    radius: Theme.rounding.extraSmall ?? 0
    container: Theme.m3inverseSurface
    color: container
    level: Metrics.snackbarElevation

    Label {
        id: label

        x: Theme.padding.large ?? 0
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - x - (actionButton.visible ? actionButton.width + (Theme.spacing.small ?? 0) : 0) - (closeButton.visible ? closeButton.width : Theme.padding.large ?? 0)
        role: "body.medium"
        text: root.text
        color: Theme.m3inverseOnSurface
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: Theme.padding.small ?? 0
        anchors.verticalCenter: parent.verticalCenter

        Button {
            id: actionButton

            objectName: "snackbar-action"
            visible: root.actionText !== ""
            type: "text"
            text: root.actionText
            contentRestColor: Theme.m3inversePrimary
            onClicked: root.action()
        }

        IconButton {
            id: closeButton

            visible: root.closable
            icon: "close"
            contentRestColor: Theme.m3inverseOnSurface
            onClicked: root.closeRequested()
        }
    }
}
