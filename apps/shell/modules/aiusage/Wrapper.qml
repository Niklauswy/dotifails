pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components

// Drawer for the AI usage panel; drops from the top-right corner.
Item {
    id: root

    required property ScreenState screenState
    required property real maxHeight

    readonly property bool shouldBeActive: screenState.aiUsage
    property real offsetScale: shouldBeActive ? 0 : 1

    visible: offsetScale < 1
    anchors.topMargin: (-implicitHeight - 5) * offsetScale
    implicitHeight: content.implicitHeight
    implicitWidth: Tokens.sizes.aiUsage.width
    opacity: 1 - offsetScale

    onShouldBeActiveChanged: {
        if (shouldBeActive)
            Qt.callLater(() => content.item?.forceActiveFocus());
    }

    Behavior on offsetScale {
        Anim {}
    }

    Loader {
        id: content

        anchors.right: parent.right
        anchors.bottom: parent.bottom

        active: root.shouldBeActive || root.visible
        focus: true

        sourceComponent: Content {
            maxHeight: root.maxHeight
            onCloseRequested: root.screenState.aiUsage = false
        }
    }
}
