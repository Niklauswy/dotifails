pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.services

// Bars over time with a value axis; hovering one reports it, clicking selects it.
Item {
    id: root

    property var values: []
    property var flags: []        // true where a bar has unpriced usage
    property var formatValue: v => String(v)
    property var xLabels: []      // three labels: start, middle, end
    property int selected: -1
    property int hovered: -1

    signal picked(int index)

    readonly property real top: {
        const max = Math.max(0, ...values);
        if (max <= 0)
            return 1;
        const magnitude = Math.pow(10, Math.floor(Math.log10(max)));
        for (const step of [1, 2, 2.5, 5, 10])
            if (step * magnitude >= max)
                return step * magnitude;
        return 10 * magnitude;
    }
    readonly property real axisWidth: axisMetrics.advanceWidth + Tokens.spacing.small
    readonly property real plotHeight: height - labels.implicitHeight - Tokens.spacing.extraSmall
    readonly property real gap: values.length > 60 ? 1 : 2

    Layout.fillWidth: true
    implicitHeight: Tokens.sizes.aiUsage.chartHeight

    TextMetrics {
        id: axisMetrics

        font: Tokens.font.label.small
        text: root.formatValue(root.top)
    }

    Repeater {
        model: [0, 0.5, 1]

        Item {
            id: grid

            required property real modelData

            x: 0
            y: root.plotHeight * (1 - modelData)
            width: root.width

            StyledText {
                anchors.verticalCenter: parent.top
                width: root.axisWidth - Tokens.spacing.small
                horizontalAlignment: Text.AlignRight
                text: root.formatValue(root.top * grid.modelData)
                font: Tokens.font.label.small
                color: Colours.palette.m3outline
            }

            Rectangle {
                x: root.axisWidth
                width: root.width - root.axisWidth
                implicitHeight: 1
                color: Colours.palette.m3outlineVariant
                opacity: grid.modelData === 0 ? 1 : 0.5
            }
        }
    }

    MouseArea {
        id: area

        x: root.axisWidth
        width: root.width - root.axisWidth
        height: root.plotHeight
        hoverEnabled: true
        readonly property int index: containsMouse && root.values.length ? Math.max(0, Math.min(root.values.length - 1, Math.floor(mouseX / width * root.values.length))) : -1
        onIndexChanged: root.hovered = index
        onClicked: if (index >= 0) root.picked(index)
        cursorShape: Qt.PointingHandCursor

        Row {
            anchors.fill: parent
            spacing: root.gap

            Repeater {
                model: root.values

                Item {
                    id: slot

                    required property real modelData
                    required property int index

                    width: Math.max(1, (area.width - root.gap * (root.values.length - 1)) / root.values.length)
                    height: area.height

                    StyledRect {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: Math.max(slot.modelData > 0 ? 2 : 1, parent.height * slot.modelData / root.top)
                        topLeftRadius: Math.min(width / 2, Tokens.rounding.extraSmall)
                        topRightRadius: topLeftRadius
                        color: slot.index === root.selected || slot.index === root.hovered ? Colours.palette.m3primary : Qt.alpha(Colours.palette.m3primary, slot.index === root.values.length - 1 ? 0.85 : 0.55)
                    }
                }
            }
        }
    }

    RowLayout {
        id: labels

        x: root.axisWidth
        width: root.width - root.axisWidth
        anchors.bottom: parent.bottom

        Repeater {
            model: root.xLabels

            StyledText {
                required property string modelData
                required property int index

                Layout.fillWidth: true
                horizontalAlignment: index === 0 ? Text.AlignLeft : index === root.xLabels.length - 1 ? Text.AlignRight : Text.AlignHCenter
                text: modelData
                font: Tokens.font.label.small
                color: Colours.palette.m3outline
            }
        }
    }
}
