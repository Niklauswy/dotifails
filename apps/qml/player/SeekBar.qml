// Position in seconds: the M3 slider with chapter gaps, the A-B loop range under the track and a time bubble that
// follows the pointer. Dragging scrubs (`scrubbed`), releasing seeks (`seekRequested`).
import QtQuick
import WysunM3

Item {
    id: root

    property real duration
    property real position
    property var chapters: []
    property var abLoop: []
    readonly property bool dragging: slider.pressed

    signal scrubbed(real seconds)
    signal seekRequested(real seconds)

    function clock(seconds) {
        const s = Math.max(0, Math.floor(seconds || 0));
        const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), r = s % 60;
        const two = n => (n < 10 ? "0" : "") + n;
        return h ? h + ":" + two(m) + ":" + two(r) : m + ":" + two(r);
    }

    function xOf(seconds) {
        return Metrics.sliderHandle / 2 + slider._track * Math.max(0, Math.min(1, seconds / Math.max(duration, 0.001)));
    }

    implicitHeight: Metrics.sliderTarget

    // A-B loop: a band under the track.
    Rectangle {
        objectName: "abRange"
        visible: root.abLoop.length > 0 && root.duration > 0
        x: root.xOf(root.abLoop[0] ?? 0)
        width: root.abLoop.length > 1 ? Math.max(Metrics.progressThickness, root.xOf(root.abLoop[1]) - x) : Metrics.progressThickness
        anchors.verticalCenter: parent.verticalCenter
        height: Metrics.sliderTrack + 2 * Metrics.progressGap
        radius: height / 2
        color: Theme.m3tertiaryContainer
    }

    Slider {
        id: slider

        objectName: "seekSlider"
        anchors.fill: parent
        from: 0
        to: Math.max(root.duration, 0.001)
        disabled: root.duration <= 0
        stepSize: 5
        pageStep: 60
        Binding on value {
            value: root.position
            when: !slider.pressed
        }
        onMoved: v => {
            if (slider.pressed)
                root.scrubbed(v);
            else
                root.seekRequested(v);
        }
        onReleased: v => root.seekRequested(v)
    }

    // Chapter starts: gaps cut into the track in the colour behind it.
    Repeater {
        model: root.duration > 0 ? root.chapters.filter(c => c > 0 && c < root.duration) : []

        Rectangle {
            required property real modelData

            x: root.xOf(modelData) - width / 2
            anchors.verticalCenter: parent.verticalCenter
            width: Metrics.progressGap / 2
            height: Metrics.sliderTrack
            color: Theme.m3surfaceContainer
        }
    }

    HoverHandler {
        id: hover
    }

    // The time under the pointer, in a plain tooltip pill above the track.
    Rectangle {
        objectName: "timeBubble"
        readonly property real at: Math.max(0, Math.min(1, (hover.point.position.x - Metrics.sliderHandle / 2) / Math.max(1, slider._track)))

        visible: (hover.hovered || slider.pressed) && root.duration > 0
        width: bubbleText.implicitWidth + 2 * (Theme.padding.small ?? 0)
        height: bubbleText.implicitHeight + (Theme.padding.extraSmall ?? 0)
        radius: Theme.rounding.extraSmall ?? 0
        color: Theme.m3inverseSurface
        x: Math.max(0, Math.min(root.width - width, (slider.pressed ? slider.handleX + Metrics.sliderHandle / 2 : hover.point.position.x) - width / 2))
        y: -height - (Theme.spacing.extraSmall ?? 0)

        Label {
            id: bubbleText

            anchors.centerIn: parent
            role: "body.small"
            color: Theme.m3inverseOnSurface
            font.features: ({tnum: 1})
            text: root.clock(slider.pressed ? slider.value : parent.at * root.duration)
        }
    }
}
