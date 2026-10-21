pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.services

StyledRect {
    id: root
    required property string label
    required property string value
    property string subtitle: "Last 60 samples"
    property var samples: []
    property real ceiling: 100
    property color tone: Colours.palette.m3primary
    color: Colours.tPalette.m3surfaceContainerHigh
    radius: Tokens.rounding.large
    implicitHeight: Tokens.spacing.extraExtraLarge * 3
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tokens.padding.medium
        spacing: Tokens.spacing.extraSmall
        StyledText { text: root.label; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.label.medium }
        StyledText { text: root.value; font: Tokens.font.title.medium; color: root.tone; Layout.fillWidth: true; elide: Text.ElideRight }
        Canvas {
            id: plot
            Layout.fillWidth: true
            Layout.fillHeight: true
            onPaint: {
                const ctx = getContext('2d'); ctx.reset();
                const values = root.samples;
                ctx.strokeStyle = root.tone; ctx.lineWidth = 2;
                ctx.beginPath();
                for (let i = 0; i < values.length; i++) {
                    const x = width * i / Math.max(1, values.length - 1);
                    const y = height - 2 - Math.min(1, Math.max(0, values[i]) / Math.max(1, root.ceiling)) * (height - 4);
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                }
                ctx.stroke();
            }
            Connections { target: root; function onSamplesChanged() { plot.requestPaint(); } function onToneChanged() { plot.requestPaint(); } }
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
        }
        StyledText { text: root.subtitle; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant; Layout.fillWidth: true; elide: Text.ElideRight }
    }
}
