// The song's position, smooth: mpv reports it at an uneven pace, so between reports it advances with the frame
// clock and eases towards each report instead of jumping; a seek or a new song snaps to it at once.
import QtQuick

FrameAnimation {
    id: root

    property real position: player.position

    running: player.playing
    onTriggered: position = Math.min(player.duration > 0 ? player.duration : Infinity, position + frameTime)

    readonly property Connections _reports: Connections {
        target: player
        function onPositionChanged() {
            const drift = player.position - root.position;
            if (!player.playing || Math.abs(drift) > 0.6)
                root.position = player.position;
            else
                root.position += drift * 0.25;
        }
    }
}
