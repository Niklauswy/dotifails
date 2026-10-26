// M3 basic dialog: interrupts with a decision. surfaceContainerHigh, extraLarge corner, 280-560 wide, centred over
// a scrim; optional hero icon (secondary), headline-small title, body-medium message, custom content (children)
// and text-button actions [{id, text, primary?}] at the end. open() moves focus to the primary action and traps
// Tab inside; Escape (or a scrim click when not `modal`) emits `rejected`; an action emits accepted(id). Focus
// returns to where it was.
import QtQuick
import WysunM3
import "OverlayHost.js" as OverlayHost

Item {
    id: root

    property string title
    property string message
    property string icon
    property var actions: []
    property bool modal: true
    property Item host
    default property alias content: contentHolder.data
    readonly property bool opened: _open
    readonly property real panelX: panel.x
    readonly property real panelY: panel.y
    readonly property real panelWidth: panel.width
    readonly property real panelRadius: panel.radius
    property bool _open
    property Item _returnFocus

    signal accepted(string id)
    signal rejected

    function open() {
        layer.parent = OverlayHost.find(root, host, Window.contentItem);
        _returnFocus = Window.activeFocusItem;
        _open = true;
        let target = null;
        for (let i = 0; i < buttons.count; ++i)
            if (!target || root.actions[i].primary)
                target = buttons.itemAt(i);
        if (target)
            target.forceActiveFocus(Qt.TabFocusReason);
        else
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
    }

    function reject() {
        if (!_open)
            return;
        close();
        rejected();
    }

    function _inside(item) {
        for (let p = item; p; p = p.parent)
            if (p === panel)
                return true;
        return false;
    }

    // The focusable items of the panel in Tab order.
    function _focusables() {
        const list = [];
        let item = panel;
        for (let i = 0; i < 1000; ++i) {
            item = item.nextItemInFocusChain(true);
            if (!item || item === panel || list.indexOf(item) >= 0)
                break;
            if (_inside(item))
                list.push(item);
        }
        return list;
    }

    // Focus trap: controls move focus along the window's chain themselves, so when it leaves the panel it is
    // brought back to the other end (Tab past the last goes to the first, Backtab before the first to the last).
    readonly property Item _focus: Window.activeFocusItem
    property Item _lastInside
    on_FocusChanged: {
        if (!_open || !_focus)
            return;
        if (_inside(_focus))
            _lastInside = _focus;
        else
            Qt.callLater(_bringBack);         // not from inside the binding that reports the change
    }
    function _bringBack() {
        if (!_open || !_focus || _inside(_focus))
            return;
        const list = _focusables();
        if (list.length === 0)
            return;
        const forward = _lastInside === list[list.length - 1];
        list[forward ? 0 : list.length - 1].forceActiveFocus(forward ? Qt.TabFocusReason : Qt.BacktabFocusReason);
    }

    Item {
        id: layer

        anchors.fill: parent
        z: 1000
        visible: root._open || panel.opacity > 0

        Rectangle {
            anchors.fill: parent
            color: Qt.alpha(Theme.m3scrim, Metrics.scrimOpacity)
            opacity: root._open ? 1 : 0

            SpringBehavior on opacity {
                kind: "defaultEffects"
            }

            MouseArea {
                anchors.fill: parent
                enabled: root._open
                acceptedButtons: Qt.AllButtons
                onClicked: {
                    if (!root.modal)
                        root.reject();
                }
            }
        }

        Surface {
            id: panel

            readonly property real limit: Math.min(Metrics.dialogMaxWidth, layer.width - 2 * (Theme.padding.extraLarge ?? 0))
            // A Column's implicit width follows its children's widths, which follow the panel: measure them instead.
            readonly property real natural: Math.max(titleLabel.implicitWidth, messageLabel.implicitWidth, contentHolder.implicitWidth, actionRow.implicitWidth)

            objectName: "dialogPanel"
            width: Math.max(Math.min(Metrics.dialogMinWidth, layer.width), Math.min(limit, natural + 2 * Metrics.dialogPadding))
            height: Math.min(layer.height - 2 * (Theme.padding.extraLarge ?? 0), column.implicitHeight + 2 * Metrics.dialogPadding)
            x: (layer.width - width) / 2
            y: (layer.height - height) / 2
            radius: Theme.rounding.extraLarge ?? 0
            container: Theme.m3surfaceContainerHigh
            color: container
            level: Metrics.dialogElevation
            clip: true
            opacity: root._open ? 1 : 0
            scale: root._open ? 1 : Metrics.menuEnterScale

            SpringBehavior on opacity {
                kind: "defaultEffects"
            }
            SpringBehavior on scale {
                kind: "defaultSpatial"
            }

            Keys.onEscapePressed: root.reject()

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
            }

            Column {
                id: column

                x: Metrics.dialogPadding
                y: Metrics.dialogPadding
                width: panel.width - 2 * Metrics.dialogPadding
                spacing: Theme.spacing.large ?? 0

                Icon {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: root.icon !== "" && available
                    name: root.icon
                    color: Theme.m3secondary
                }

                Label {
                    id: titleLabel

                    width: parent.width
                    visible: root.title !== ""
                    role: "headline.small"
                    text: root.title
                    wrapMode: Text.Wrap
                    horizontalAlignment: root.icon !== "" ? Text.AlignHCenter : Text.AlignLeft
                }

                Label {
                    id: messageLabel

                    width: parent.width
                    visible: root.message !== ""
                    role: "body.medium"
                    text: root.message
                    color: Theme.m3onSurfaceVariant
                    wrapMode: Text.Wrap
                }

                Item {
                    id: contentHolder

                    width: parent.width
                    implicitWidth: childrenRect.width
                    implicitHeight: childrenRect.height
                    height: implicitHeight
                    visible: children.length > 0
                }

                Row {
                    id: actionRow

                    anchors.right: parent.right
                    visible: root.actions.length > 0
                    spacing: Theme.spacing.small ?? 0

                    Repeater {
                        id: buttons

                        model: root.actions

                        Button {
                            required property var modelData

                            objectName: "action-" + modelData.id
                            type: "text"
                            text: modelData.text ?? ""
                            onClicked: {
                                root.close();
                                root.accepted(modelData.id);
                            }
                        }
                    }
                }
            }
        }
    }
}
