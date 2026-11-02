import QtQuick
import Wysun.Config
import "../../utils/CameraBubble.js" as Bubble
import qs.components
import qs.services

// A solid shape where the camera will cover the recording: same corner, size and shape as the bubble, `inset` pixels
// smaller on every side so no edge of it peeks out from under the camera. It is drawn on the recorded screen, and the
// camera is composited over it afterwards, so it never shows in the video; it only tells the person what the camera
// will hide. `area` is the recorded area on its output.
Item {
    id: root

    required property rect area
    required property var style
    property real inset: 2
    readonly property var bubble: Bubble.rect(area.width, area.height, style)
    readonly property alias shape: shape

    Rectangle {
        id: shape

        x: root.area.x + root.bubble.x + root.inset
        y: root.area.y + root.bubble.y + root.inset
        width: root.bubble.width - root.inset * 2
        height: root.bubble.height - root.inset * 2
        radius: Math.max(0, root.bubble.radius - root.inset)
        color: Colours.palette.m3primary

        MaterialIcon {
            anchors.centerIn: parent
            text: "videocam"
            color: Colours.palette.m3onPrimary
            fontStyle: Tokens.font.icon.large
        }
    }
}
