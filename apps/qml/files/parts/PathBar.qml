// The path (F-12): navigable segments from «Inicio» or «Sistema», the last one as a filled pill; long paths keep
// their end in view. Ctrl+L turns it into a field (Enter goes, Escape cancels); a right click on a segment offers
// to copy its path without going there.
import QtQuick
import WysunM3

Item {
    id: root

    property var tab
    property bool editing
    readonly property alias field: edit
    signal navigateRequested(string path)
    signal copyRequested(string path)
    signal editFinished

    function begin() {
        edit.text = tab ? tab.path : "";
        editing = true;
        edit.forceActiveFocus();
        edit.selectAll();
    }

    function finish() {
        editing = false;
        editFinished();
    }

    implicitHeight: Metrics.buttonHeight

    ListView {
        id: crumbs

        objectName: "crumbs"
        anchors.fill: parent
        visible: !root.editing
        orientation: ListView.Horizontal
        clip: true
        interactive: contentWidth > width
        boundsBehavior: Flickable.StopAtBounds
        model: root.tab ? root.tab.crumbs : []
        onCountChanged: Qt.callLater(positionViewAtEnd)
        onWidthChanged: Qt.callLater(positionViewAtEnd)

        delegate: Row {
            id: crumb

            required property var modelData
            required property int index
            readonly property bool last: index === crumbs.count - 1

            height: crumbs.height
            spacing: 0

            Icon {
                visible: crumb.index > 0
                anchors.verticalCenter: parent.verticalCenter
                name: "chevron_right"
                size: Metrics.buttonIconSize
                color: Theme.m3onSurfaceVariant
            }
            Item {
                anchors.verticalCenter: parent.verticalCenter
                width: content.implicitWidth + 2 * (Theme.padding.small ?? 0)
                height: Metrics.buttonHeight - (Theme.spacing.small ?? 0)

                Rectangle {
                    anchors.fill: parent
                    radius: height / 2
                    color: crumb.last ? Theme.m3secondaryContainer : "transparent"
                }
                StateLayer {
                    anchors.fill: parent
                    radius: height / 2
                    tint: crumb.last ? Theme.m3onSecondaryContainer : Theme.m3onSurface
                    mouseArea.acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: mouse => mouse.button === Qt.RightButton ? root.copyRequested(crumb.modelData.path) : root.navigateRequested(crumb.modelData.path)
                }
                Row {
                    id: content

                    anchors.centerIn: parent
                    spacing: Theme.spacing.extraSmall ?? 0

                    Icon {
                        visible: crumb.modelData.icon !== ""
                        anchors.verticalCenter: parent.verticalCenter
                        name: crumb.modelData.icon
                        size: Metrics.buttonIconSize
                        color: crumb.last ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
                    }
                    Label {
                        anchors.verticalCenter: parent.verticalCenter
                        role: "title.small"
                        text: crumb.modelData.label
                        color: crumb.last ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
                    }
                }
            }
        }

        // Clicking the empty part of the bar edits the path, like Ctrl+L.
        MouseArea {
            z: -1
            x: crumbs.contentWidth
            width: Math.max(0, crumbs.width - crumbs.contentWidth)
            height: crumbs.height
            onClicked: root.begin()
        }
    }

    Rectangle {
        visible: root.editing
        anchors.fill: parent
        radius: height / 2
        color: Theme.m3surfaceContainerHigh
        border.width: Metrics.textFieldFocusWidth
        border.color: Theme.m3primary

        Icon {
            id: pencil

            x: Theme.padding.medium ?? 0
            anchors.verticalCenter: parent.verticalCenter
            name: "edit"
            size: Metrics.buttonIconSize
            color: Theme.m3onSurfaceVariant
        }
        TextInput {
            id: edit

            objectName: "pathField"
            anchors.left: pencil.right
            anchors.leftMargin: Theme.spacing.small ?? 0
            anchors.right: parent.right
            anchors.rightMargin: Theme.padding.medium ?? 0
            anchors.verticalCenter: parent.verticalCenter
            clip: true
            font.family: Theme.typeFont("body.large").family
            font.pointSize: Math.max(1, Theme.typeFont("body.large").pointSize)
            color: Theme.m3onSurface
            selectionColor: Theme.m3primary
            selectedTextColor: Theme.m3onPrimary
            onAccepted: root.navigateRequested(text)
            onActiveFocusChanged: if (!activeFocus && root.editing) root.finish()
            Keys.onEscapePressed: event => {
                root.finish();
                event.accepted = true;
            }
        }
    }
}
