// The transport of a video or a song in the preview: the position with its times, ten seconds back or forward, and
// play / pause, on the window's single MediaPlayer. A song gets the wavy track, moving while it plays.
import QtQuick
import QtMultimedia
import WysunM3

Column {
    id: root

    property var player
    property bool wavy
    readonly property bool playing: player !== null && player !== undefined && player.playbackState === MediaPlayer.PlayingState

    function clock(ms) {
        const s = Math.floor(Math.max(0, ms) / 1000);
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }

    function seek(delta) {
        player.position = Math.max(0, Math.min(player.duration, player.position + delta));
    }

    spacing: Theme.spacing.extraSmall ?? 0

    Slider {
        objectName: "previewSlider"
        width: parent.width
        from: 0
        to: Math.max(1, root.player ? root.player.duration : 1)
        value: root.player ? root.player.position : 0
        wavy: root.wavy
        waveMoving: root.wavy && root.playing
        onMoved: v => {
            if (root.player)
                root.player.position = v;
        }
        // Dragging assigns `value`; follow the player again afterwards.
        onReleased: value = Qt.binding(() => root.player ? root.player.position : 0)
    }
    Item {
        width: parent.width
        height: elapsed.implicitHeight

        Label {
            id: elapsed

            role: "label.medium"
            text: root.clock(root.player ? root.player.position : 0)
            color: Theme.m3onSurfaceVariant
        }
        Label {
            anchors.right: parent.right
            role: "label.medium"
            text: root.clock(root.player ? root.player.duration : 0)
            color: Theme.m3onSurfaceVariant
        }
    }
    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Theme.spacing.medium ?? 0

        IconButton {
            anchors.verticalCenter: parent.verticalCenter
            icon: "replay_10"
            onClicked: root.seek(-10000)
        }
        Fab {
            objectName: "previewPlay"
            variant: "primary"
            icon: root.playing ? "pause" : "play_arrow"
            onClicked: root.playing ? root.player.pause() : root.player.play()
        }
        IconButton {
            anchors.verticalCenter: parent.verticalCenter
            icon: "forward_10"
            onClicked: root.seek(10000)
        }
    }
}
