// M3 segmented buttons: pick one option (`current`) or several (`multiSelect`, `selection`) from 2-5 related
// ones, e.g. a view mode. model: [{value, text, icon}]. 40 high, 1 dp outline, all segments as wide as the
// widest; a selected segment is secondaryContainer and shows a check instead of its icon.
import QtQuick
import WysunM3

Item {
    id: root

    property var model: []
    property bool multiSelect
    property string current
    property var selection: []
    property bool disabled

    signal activated(string value)

    readonly property real _segment: {
        let widest = 0;
        for (let i = 0; i < measure.count; ++i)
            widest = Math.max(widest, measure.itemAt(i)?.implicitWidth ?? 0);
        return widest + 2 * Metrics.buttonPadding;
    }

    function isSelected(value) {
        return multiSelect ? (selection ?? []).indexOf(value) >= 0 : current === value;
    }

    function iconOf(value) {
        for (const option of model)
            if (option.value === value)
                return isSelected(value) ? "check" : option.icon ?? "";
        return "";
    }

    function segmentWidths() {
        const widths = [];
        for (let i = 0; i < segments.count; ++i)
            widths.push(segments.itemAt(i).width);
        return widths;
    }

    function toggle(value) {
        if (disabled)
            return;
        if (multiSelect) {
            const next = (selection ?? []).slice();
            const at = next.indexOf(value);
            if (at >= 0)
                next.splice(at, 1);
            else
                next.push(value);
            selection = next;
        } else {
            current = value;
        }
        activated(value);
    }

    implicitWidth: _segment * model.length
    implicitHeight: Metrics.segmentedHeight
    width: implicitWidth
    height: implicitHeight

    // Invisible copies of each segment's content: the widest sets every segment's width.
    Repeater {
        id: measure

        model: root.model

        Row {
            required property var modelData

            visible: false
            spacing: Theme.spacing.small ?? 0

            Icon {
                size: Metrics.buttonIconSize
                name: "check"
            }
            Label {
                role: "label.large"
                text: modelData.text ?? ""
            }
        }
    }

    Item {
        anchors.fill: parent

        Repeater {
            id: segments

            model: root.model

            Rectangle {
                id: segment

                required property var modelData
                required property int index
                readonly property bool first: index === 0
                readonly property bool last: index === root.model.length - 1
                readonly property bool selected: root.isSelected(modelData.value)
                readonly property real outer: Theme.fullRadius(height)
                readonly property color content: root.disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContent) : selected ? Theme.m3onSecondaryContainer : Theme.m3onSurface

                width: root._segment
                height: root.height
                topLeftRadius: first ? outer : 0
                bottomLeftRadius: first ? outer : 0
                topRightRadius: last ? outer : 0
                bottomRightRadius: last ? outer : 0
                color: selected && !root.disabled ? Theme.m3secondaryContainer : "transparent"
                border.width: Metrics.outlineWidth
                border.color: root.disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledOutline) : Theme.m3outline
                focusPolicy: root.disabled ? Qt.NoFocus : Qt.TabFocus
                activeFocusOnTab: !root.disabled
                Keys.onSpacePressed: root.toggle(modelData.value)
                Keys.onReturnPressed: root.toggle(modelData.value)
                Keys.onEnterPressed: root.toggle(modelData.value)

                // Neighbours share one outline: each segment after the first overlaps the previous one by it.
                x: index * (root._segment - Metrics.outlineWidth)

                Behavior on color {
                    CAnim {
                        kind: "fastEffects"
                    }
                }

                Row {
                    anchors.centerIn: parent
                    spacing: Theme.spacing.small ?? 0

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        size: Metrics.buttonIconSize
                        name: root.iconOf(segment.modelData.value)
                        visible: name !== "" && available
                        color: segment.content
                    }
                    Label {
                        anchors.verticalCenter: parent.verticalCenter
                        role: "label.large"
                        text: segment.modelData.text ?? ""
                        color: segment.content
                    }
                }

                StateLayer {
                    tint: segment.content
                    ripple: false
                    topLeftRadius: segment.topLeftRadius
                    bottomLeftRadius: segment.bottomLeftRadius
                    topRightRadius: segment.topRightRadius
                    bottomRightRadius: segment.bottomRightRadius
                    disabled: root.disabled
                    focused: segment.activeFocus
                    onClicked: root.toggle(segment.modelData.value)
                }

                FocusRing {
                    target: segment
                    radius: segment.outer
                }
            }
        }
    }
}
