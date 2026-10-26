// M3 tooltip for its parent (or `target`): after hovering it for the `normal` duration token, a plain tooltip
// (inverseSurface, extraSmall corner, 24 high, body-small) appears below it, above when there is no room; `rich`
// adds a title on a surfaceContainer card with the medium corner. Leaving the target hides it.
import QtQuick
import WysunM3
import "OverlayHost.js" as OverlayHost

Item {
    id: root

    property string text
    property string title
    property bool rich
    property Item target: parent
    property Item host
    readonly property int delay: Theme.duration("normal")
    readonly property bool shown: _shown
    readonly property real panelHeight: panel.height
    property bool _shown

    function show() {
        if (!target)
            return;
        const top = OverlayHost.find(root, host, Window.contentItem);
        layer.parent = top;
        const gap = Theme.spacing.extraSmall ?? 0;
        const margin = Theme.padding.small ?? 0;
        const below = target.mapToItem(top, target.width / 2, target.height + gap);
        const above = target.mapToItem(top, target.width / 2, -gap - panel.height);
        const y = below.y + panel.height <= top.height - margin ? below.y : above.y;
        panel.x = Math.max(margin, Math.min(below.x - panel.width / 2, top.width - panel.width - margin));
        panel.y = Math.max(margin, y);
        _shown = true;
    }

    function hide() {
        timer.stop();
        _shown = false;
    }

    HoverHandler {
        id: hover

        parent: root.target
        onHoveredChanged: {
            if (hovered)
                timer.restart();
            else
                root.hide();
        }
    }

    Timer {
        id: timer

        interval: root.delay
        onTriggered: root.show()
    }

    Item {
        id: layer

        z: 1001
        anchors.fill: parent
        visible: root._shown || panel.opacity > 0

        Rectangle {
            id: panel

            objectName: "tooltipPanel"
            // The column's labels take its width, so the rich width is measured from their implicit widths.
            width: root.rich ? Math.min(Metrics.richTooltipMaxWidth, Math.max(richTitle.implicitWidth, richBody.implicitWidth) + 2 * (Theme.padding.large ?? 0)) : plain.implicitWidth + 2 * (Theme.padding.small ?? 0)
            height: root.rich ? richColumn.implicitHeight + 2 * (Theme.padding.medium ?? 0) : Metrics.tooltipHeight
            radius: root.rich ? Theme.rounding.medium ?? 0 : Theme.rounding.extraSmall ?? 0
            color: root.rich ? Theme.m3surfaceContainer : Theme.m3inverseSurface
            opacity: root._shown ? 1 : 0

            SpringBehavior on opacity {
                kind: "fastEffects"
            }

            Label {
                id: plain

                visible: !root.rich
                anchors.centerIn: parent
                role: "body.small"
                text: root.text
                color: Theme.m3inverseOnSurface
            }

            Column {
                id: richColumn

                visible: root.rich
                x: Theme.padding.large ?? 0
                y: Theme.padding.medium ?? 0
                width: parent.width - 2 * x
                spacing: Theme.spacing.extraSmall ?? 0

                Label {
                    id: richTitle

                    width: parent.width
                    visible: root.title !== ""
                    role: "title.small"
                    text: root.title
                    color: Theme.m3onSurfaceVariant
                }
                Label {
                    id: richBody

                    width: parent.width
                    role: "body.medium"
                    text: root.text
                    color: Theme.m3onSurfaceVariant
                    wrapMode: Text.Wrap
                }
            }
        }
    }
}
