// A live chart of the last `capacity` samples (CPU, memory, traffic…). New samples slide in continuously over
// `interval` ms instead of jumping; the first series gets a gradient fill. With `scrub`, the pointer shows a guide,
// a dot and a label (`formatValue(value)` and `labelAt(index)`), and `markers` ([{index, color, glyph}]) pin a
// small badge on chosen samples (e.g. the app that caused a peak). Colours come from the theme (pass roles in
// `colors`). Use for time series; not for comparing categories.
import QtQuick
import WysunM3

Item {
    id: root

    property var series: []
    property var colors: [Theme.m3primary]
    property real maxValue: 0                       // 0: fit to the data
    property int capacity: 60
    property int interval: 1000
    property bool grid: true
    property bool fill: true
    property bool dot: true
    property real lineWidth: 2.5
    property real pad: Theme.spacing.small ?? 0
    property bool scrub: false
    property var markers: []
    property var formatValue: v => String(Math.round(v))
    property var labelAt: i => ""
    property real progress: 1
    readonly property var first: series && series.length ? series[0] : []
    readonly property real effectiveMax: maxValue > 0 ? maxValue : largest(series) * 1.2
    readonly property int hoverIndex: hover.hovered && scrub && first.length ? indexAt(hover.point.position.x) : -1
    readonly property string hoverText: hoverIndex < 0 ? "" : [labelAt(hoverIndex), formatValue(first[hoverIndex])].filter(t => t !== "").join(" · ")

    signal hovered(int index)

    function largest(list): real {
        let top = 1;
        for (let s = 0; s < (list?.length ?? 0); s++)
            for (let i = 0; i < (list[s]?.length ?? 0); i++)
                top = Math.max(top, Number(list[s][i]) || 0);
        return top;
    }
    function step(): real {
        return width / Math.max(1, capacity - 1);
    }
    function xAt(i: int, n: int): real {
        return (i - (n - capacity) + (1 - progress)) * step();
    }
    function yAt(v: real): real {
        return height - pad - Math.min(v, effectiveMax) / effectiveMax * (height - pad * 2);
    }
    function indexAt(x: real): int {
        const n = first.length;
        const i = Math.round(x / step() - (1 - progress)) + (n - capacity);
        return Math.max(0, Math.min(n - 1, i));
    }

    property bool _ready: false
    readonly property bool _reduced: Motion.reduced

    on_ReducedChanged: if (_reduced) {
        slide.stop();
        progress = 1;
    }
    Component.onCompleted: _ready = true
    onHoverIndexChanged: hovered(hoverIndex)
    onSeriesChanged: {
        if (Motion.reduced || !_ready) {
            progress = 1;
            return;
        }
        slide.stop();
        progress = 0;
        slide.start();
    }
    onProgressChanged: canvas.requestPaint()
    onWidthChanged: canvas.requestPaint()
    onHeightChanged: canvas.requestPaint()
    onColorsChanged: canvas.requestPaint()
    onMarkersChanged: canvas.requestPaint()

    NumberAnimation {
        id: slide

        target: root
        property: "progress"
        from: 0
        to: 1
        duration: Motion.reduced ? 0 : root.interval
        easing.type: Easing.Linear
    }

    Canvas {
        id: canvas

        anchors.fill: parent
        renderStrategy: Canvas.Cooperative

        onPaint: {
            const g = getContext("2d");
            g.reset();
            if (root.grid) {
                g.strokeStyle = Theme.m3outlineVariant;
                g.lineWidth = 1;
                for (let i = 1; i < 4; i++) {
                    const y = Math.round(height * i / 4) + 0.5;
                    g.beginPath();
                    g.moveTo(0, y);
                    g.lineTo(width, y);
                    g.stroke();
                }
            }
            const list = root.series ?? [];
            for (let s = list.length - 1; s >= 0; s--) {
                const data = list[s] ?? [];
                const n = data.length;
                if (n < 2)
                    continue;
                const c = root.colors[s] ?? root.colors[0] ?? Theme.m3primary;
                g.beginPath();
                let px = root.xAt(0, n), py = root.yAt(data[0]);
                g.moveTo(px, py);
                for (let i = 1; i < n; i++) {
                    const x = root.xAt(i, n), y = root.yAt(data[i]);
                    const mx = (px + x) / 2;
                    g.bezierCurveTo(mx, py, mx, y, x, y);
                    px = x;
                    py = y;
                }
                g.strokeStyle = c;
                g.lineWidth = root.lineWidth;
                g.lineJoin = "round";
                g.stroke();
                if (s === 0 && root.fill) {
                    g.lineTo(px, height);
                    g.lineTo(root.xAt(0, n), height);
                    g.closePath();
                    const gradient = g.createLinearGradient(0, 0, 0, height);
                    gradient.addColorStop(0, Qt.alpha(c, 0.38));
                    gradient.addColorStop(1, Qt.alpha(c, 0));
                    g.fillStyle = gradient;
                    g.fill();
                }
                if (s === 0 && root.dot) {
                    g.beginPath();
                    g.arc(px, py, root.lineWidth * 3.2, 0, Math.PI * 2);
                    g.fillStyle = Qt.alpha(c, 0.25);
                    g.fill();
                    g.beginPath();
                    g.arc(px, py, root.lineWidth * 1.6, 0, Math.PI * 2);
                    g.fillStyle = c;
                    g.fill();
                }
            }
        }
    }

    // Peak markers: a badge over the sample, its glyph (e.g. the app's initial) or an icon.
    Repeater {
        model: root.markers ?? []

        Rectangle {
            required property var modelData
            readonly property int n: root.first.length
            readonly property real px: root.xAt(modelData.index, n)

            visible: modelData.index >= 0 && modelData.index < n && px > width / 2 && px < root.width - width / 2
            width: (Theme.spacing.large ?? 0) + (Theme.spacing.small ?? 0)
            height: width
            radius: width / 2
            color: modelData.color ?? Theme.m3secondaryContainer
            x: px - width / 2
            y: Math.max(0, root.yAt(root.first[modelData.index] ?? 0) - height - (Theme.spacing.small ?? 0))

            Image {
                anchors.centerIn: parent
                width: parent.width * 0.7
                height: width
                visible: !!parent.modelData.icon
                source: parent.modelData.icon ?? ""
                sourceSize.width: width
                sourceSize.height: height
            }

            Label {
                anchors.centerIn: parent
                visible: !parent.modelData.icon
                text: parent.modelData.glyph ?? ""
                role: "label.small"
                color: Theme.m3onSecondaryContainer
            }
        }
    }

    // Scrub guide, dot and label.
    Rectangle {
        visible: root.hoverIndex >= 0
        x: root.hoverIndex >= 0 ? root.xAt(root.hoverIndex, root.first.length) : 0
        width: 1
        height: parent.height
        color: Theme.m3outline
    }

    Rectangle {
        visible: root.hoverIndex >= 0
        width: root.lineWidth * 5
        height: width
        radius: width / 2
        color: Theme.m3surface
        border.width: root.lineWidth
        border.color: root.colors[0] ?? Theme.m3primary
        x: (root.hoverIndex >= 0 ? root.xAt(root.hoverIndex, root.first.length) : 0) - width / 2
        y: (root.hoverIndex >= 0 ? root.yAt(root.first[root.hoverIndex]) : 0) - height / 2
    }

    Rectangle {
        id: tip

        visible: root.hoverIndex >= 0
        z: 3
        width: tipLabel.implicitWidth + (Theme.padding.normal ?? 0) * 2
        height: tipLabel.implicitHeight + (Theme.padding.small ?? 0) * 2
        radius: Theme.rounding.small ?? 0
        color: Theme.m3inverseSurface
        x: Math.max(0, Math.min(root.width - width, (root.hoverIndex >= 0 ? root.xAt(root.hoverIndex, root.first.length) : 0) - width / 2))
        y: Math.max(0, (root.hoverIndex >= 0 ? root.yAt(root.first[root.hoverIndex]) : 0) - height - (Theme.spacing.normal ?? 0))

        Label {
            id: tipLabel

            anchors.centerIn: parent
            text: root.hoverText
            role: "label.medium"
            color: Theme.m3inverseOnSurface
        }
    }

    HoverHandler {
        id: hover

        enabled: root.scrub
    }
}
