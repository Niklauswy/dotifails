// A thin vertical scroll indicator for a Flickable: it shows while scrolling or hovered, the thumb can be dragged
// and a click on the track pages towards it. Use beside long lists and panels; Files keeps its own copy.
import QtQuick
import WysunM3

Item {
    id: root

    property Flickable flickable
    readonly property real ratio: flickable ? Math.min(1, flickable.visibleArea.heightRatio) : 1
    readonly property bool needed: ratio < 1
    readonly property bool active: hover.containsMouse || drag.dragging || (flickable?.moving ?? false)

    width: Theme.spacing.medium ?? 0
    visible: needed
    opacity: active ? 1 : 0.35

    Behavior on opacity {
        Anim {
            kind: "fastEffects"
        }
    }

    MouseArea {
        id: hover

        anchors.fill: parent
        hoverEnabled: true
        onPressed: mouse => {
            const page = root.flickable.height * 0.9;
            const down = mouse.y > thumb.y + thumb.height;
            const max = root.flickable.contentHeight - root.flickable.height + root.flickable.originY;
            root.flickable.contentY = Math.max(root.flickable.originY, Math.min(max, root.flickable.contentY + (down ? page : -page)));
        }
    }
    Rectangle {
        id: thumb

        x: (root.width - width) / 2
        width: root.active ? root.width * 0.6 : root.width * 0.35
        height: Math.max(Metrics.chipHeight, root.height * root.ratio)
        y: root.flickable ? Math.max(0, Math.min(root.height - height, root.flickable.visibleArea.yPosition * root.height)) : 0
        radius: width / 2
        color: root.active ? Theme.m3onSurfaceVariant : Theme.m3outline

        Behavior on width {
            Anim {
                kind: "fastSpatial"
            }
        }

        MouseArea {
            id: drag

            property real grab
            readonly property bool dragging: pressed

            anchors.fill: parent
            // No drag.target: the thumb stays bound to the flickable, the flickable follows the pointer.
            onPressed: mouse => grab = mouse.y
            onPositionChanged: mouse => {
                if (!pressed || root.height <= thumb.height)
                    return;
                const y = Math.max(0, Math.min(root.height - thumb.height, thumb.y + mouse.y - grab));
                const span = root.flickable.contentHeight - root.flickable.height;
                root.flickable.contentY = root.flickable.originY + span * y / (root.height - thumb.height);
            }
        }
    }
}
