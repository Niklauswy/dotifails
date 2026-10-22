pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.services

// Smooth area chart, one series per provider: [{ values: [...], colour }].
Item {
    id: root

    property var series: []
    property var xLabels: []
    property var formatValue: v => String(v)
    property color gridColour: Colours.palette.m3outlineVariant

    readonly property real maxValue: {
        let max = 0;
        for (const s of series)
            for (const v of s.values)
                max = Math.max(max, v);
        return niceCeil(max);
    }
    readonly property var ticks: [0, maxValue / 4, maxValue / 2, maxValue * 3 / 4, maxValue]
    // The top tick has the widest label.
    readonly property real labelWidth: metrics.advanceWidth + Tokens.spacing.small
    readonly property real plotX: labelWidth
    readonly property real plotWidth: width - labelWidth
    readonly property real plotHeight: height - xAxis.height - Tokens.spacing.extraSmall

    function niceCeil(value: real): real {
        if (value <= 0)
            return 1;
        const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
        for (const step of [1, 2, 2.5, 5, 10])
            if (step * magnitude >= value)
                return step * magnitude;
        return 10 * magnitude;
    }

    function yFor(value: real): real {
        return plotHeight - value / maxValue * plotHeight;
    }

    onSeriesChanged: canvas.requestPaint()
    onGridColourChanged: canvas.requestPaint()

    TextMetrics {
        id: metrics

        font: Tokens.font.label.small
        text: root.formatValue(root.maxValue)
    }

    Repeater {
        model: root.ticks

        StyledText {
            required property real modelData

            x: 0
            y: root.yFor(modelData) - height / 2
            width: root.labelWidth - Tokens.spacing.small
            horizontalAlignment: Text.AlignRight
            text: root.formatValue(modelData)
            font: Tokens.font.label.small
            color: Colours.palette.m3outline
        }
    }

    Canvas {
        id: canvas

        // Monotone cubic interpolation keeps peaks smooth without dipping below zero.
        function drawSeries(ctx, s): void {
            const n = s.values.length;
            if (n < 2)
                return;
            const step = width / (n - 1);
            const pts = s.values.map((v, i) => ({ x: i * step, y: root.yFor(v) }));
            const slopes = [];
            for (let i = 0; i < n - 1; i++)
                slopes.push((pts[i + 1].y - pts[i].y) / step);
            const tangents = [slopes[0]];
            for (let i = 1; i < n - 1; i++)
                tangents.push(slopes[i - 1] * slopes[i] <= 0 ? 0 : (slopes[i - 1] + slopes[i]) / 2);
            tangents.push(slopes[n - 2]);
            for (let i = 0; i < n - 1; i++) {
                if (slopes[i] === 0) {
                    tangents[i] = tangents[i + 1] = 0;
                    continue;
                }
                const a = tangents[i] / slopes[i], b = tangents[i + 1] / slopes[i], h = a * a + b * b;
                if (h > 9) {
                    const k = 3 / Math.sqrt(h);
                    tangents[i] = k * a * slopes[i];
                    tangents[i + 1] = k * b * slopes[i];
                }
            }
            const path = () => {
                ctx.moveTo(pts[0].x, pts[0].y);
                for (let i = 0; i < n - 1; i++)
                    ctx.bezierCurveTo(pts[i].x + step / 3, pts[i].y + tangents[i] * step / 3, pts[i + 1].x - step / 3, pts[i + 1].y - tangents[i + 1] * step / 3, pts[i + 1].x, pts[i + 1].y);
            };

            ctx.beginPath();
            path();
            ctx.lineTo(width, root.plotHeight);
            ctx.lineTo(0, root.plotHeight);
            ctx.closePath();
            ctx.fillStyle = Qt.alpha(s.colour, 0.18);
            ctx.fill();

            ctx.beginPath();
            path();
            ctx.lineWidth = Tokens.sizes.aiUsage.chartLineWidth;
            ctx.strokeStyle = s.colour;
            ctx.stroke();
        }

        x: root.plotX
        width: root.plotWidth
        height: root.plotHeight + 1
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            ctx.lineWidth = 1;
            ctx.strokeStyle = root.gridColour;
            for (const t of root.ticks) {
                const y = Math.round(root.yFor(t)) + 0.5;
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(width, y);
                ctx.stroke();
            }
            for (const s of root.series)
                drawSeries(ctx, s);
        }
    }

    Item {
        id: xAxis

        x: root.plotX
        y: root.plotHeight + Tokens.spacing.extraSmall
        width: root.plotWidth
        height: metrics.height

        Repeater {
            model: root.xLabels

            StyledText {
                required property var modelData
                required property int index

                x: Math.max(0, Math.min(xAxis.width - width, modelData.position * xAxis.width - width / 2))
                text: modelData.text
                font: Tokens.font.label.small
                color: Colours.palette.m3outline
            }
        }
    }
}
