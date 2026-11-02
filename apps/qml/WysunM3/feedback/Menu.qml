// M3 menu: a list of choices on a temporary surface (surfaceContainer, extraSmall corner, level 2) that grows in
// from its anchor corner. model: [{id, text, icon?, shortcut?, disabled?}] and {divider: true}. popup(item, x, y)
// opens it at that point of `item`, flipped and clamped to stay inside the host. ↑/↓ (wrapping, skipping dividers
// and disabled rows), Enter/Space trigger, Escape or a click outside close it; focus returns where it was.
import QtQuick
import WysunM3
import "OverlayHost.js" as OverlayHost

Item {
    id: root

    property var model: []
    property Item host
    property int currentIndex: -1
    readonly property bool opened: _open
    readonly property real panelX: panel.x
    readonly property real panelY: panel.y
    readonly property real panelWidth: panel.width
    readonly property real panelHeight: panel.height
    readonly property real panelRadius: panel.radius
    property bool _open
    property Item _returnFocus

    signal triggered(string id)
    signal closed

    function _usable(index) {
        const entry = model[index];
        return !!entry && !entry.divider && !entry.disabled;
    }

    function _step(delta) {
        const n = model.length;
        for (let i = 1; i <= n; ++i) {
            const index = ((currentIndex < 0 ? (delta > 0 ? -1 : 0) : currentIndex) + delta * i + n * n) % n;
            if (_usable(index)) {
                currentIndex = index;
                return;
            }
        }
    }

    function popup(item, x, y) {
        const target = OverlayHost.find(root, host, Window.contentItem);
        layer.parent = target;
        column.forceLayout();                   // a model set just before must be measured before placing
        const point = (item ?? root).mapToItem(target, x ?? 0, y ?? 0);
        const margin = Theme.padding.small ?? 0;
        let px = point.x;
        let py = point.y;
        let originX = 0;
        let originY = 0;
        if (px + panel.width > target.width - margin) {
            px = point.x - panel.width;
            originX = 1;
        }
        if (py + panel.height > target.height - margin) {
            py = point.y - panel.height;
            originY = 1;
        }
        panel.x = Math.max(margin, Math.min(px, target.width - panel.width - margin));
        panel.y = Math.max(margin, Math.min(py, target.height - panel.height - margin));
        panel.transformOrigin = originY ? (originX ? Item.BottomRight : Item.BottomLeft) : (originX ? Item.TopRight : Item.TopLeft);
        _returnFocus = Window.activeFocusItem;
        currentIndex = -1;
        _step(1);
        _open = true;
        panel.forceActiveFocus();
    }

    function close() {
        if (!_open)
            return;
        _open = false;
        const back = _returnFocus;
        _returnFocus = null;
        if (back)
            back.forceActiveFocus(Qt.TabFocusReason);
        closed();
    }

    function trigger(index) {
        if (!_usable(index))
            return;
        const id = model[index].id;
        close();
        triggered(id);
    }

    Item {
        id: layer

        anchors.fill: parent
        z: 1000
        visible: root._open || panel.opacity > 0

        MouseArea {
            anchors.fill: parent
            enabled: root._open
            acceptedButtons: Qt.AllButtons
            onPressed: root.close()
        }

        Surface {
            id: panel

            objectName: "menuPanel"
            width: Math.max(Metrics.menuMinWidth, Math.min(Metrics.menuMaxWidth, column.widest))
            height: column.implicitHeight + 2 * (Theme.padding.small ?? 0)
            radius: Theme.rounding.extraSmall ?? 0
            container: Theme.m3surfaceContainer
            color: container
            level: Metrics.menuElevation
            opacity: root._open ? 1 : 0
            scale: root._open ? 1 : Metrics.menuEnterScale

            SpringBehavior on opacity {
                kind: "fastEffects"
            }
            SpringBehavior on scale {
                kind: "fastSpatial"
            }

            Keys.onPressed: event => {
                switch (event.key) {
                case Qt.Key_Up:
                    root._step(-1);
                    break;
                case Qt.Key_Down:
                    root._step(1);
                    break;
                case Qt.Key_Return:
                case Qt.Key_Enter:
                case Qt.Key_Space:
                    root.trigger(root.currentIndex);
                    break;
                case Qt.Key_Escape:
                    root.close();
                    break;
                default:
                    return;
                }
                event.accepted = true;
            }

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
            }

            Column {
                id: column

                // The widest row sets the panel width; follows model changes (count) in both directions.
                readonly property real widest: {
                    let widest = 0;
                    for (let i = 0; i < entries.count; ++i)
                        widest = Math.max(widest, entries.itemAt(i)?.contentWidth ?? 0);
                    return widest;
                }

                y: Theme.padding.small ?? 0
                width: parent.width

                Repeater {
                    id: entries

                    model: root.model

                    Item {
                        id: entry

                        required property var modelData
                        required property int index
                        readonly property real contentWidth: modelData.divider ? 0 : row.contentWidth

                        width: column.width
                        height: modelData.divider ? 2 * (Theme.padding.small ?? 0) + Metrics.outlineWidth : Metrics.menuItemHeight

                        Divider {
                            visible: !!entry.modelData.divider
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width
                        }

                        MenuItem {
                            id: row

                            visible: !entry.modelData.divider
                            width: parent.width
                            entry: entry.modelData
                            current: root.currentIndex === entry.index
                            onTriggered: root.trigger(entry.index)
                            onHovered: {
                                if (!disabled)
                                    root.currentIndex = entry.index;
                            }
                        }
                    }
                }
            }
        }
    }
}
