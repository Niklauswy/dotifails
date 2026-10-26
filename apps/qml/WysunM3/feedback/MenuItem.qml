// One row of a Menu: 48 high, optional 24 px leading icon, body-large label, trailing shortcut hint.
// entry: {id, text, icon?, shortcut?, disabled?}
import QtQuick
import WysunM3

Item {
    id: root

    property var entry: ({})
    property bool current
    readonly property bool disabled: !!entry.disabled
    readonly property color contentColor: disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContent) : Theme.m3onSurface
    readonly property real contentWidth: row.implicitWidth + (shortcut.visible ? 2 * (Theme.spacing.medium ?? 0) + shortcut.implicitWidth : 0) + 2 * (Theme.padding.medium ?? 0)

    signal triggered
    signal hovered

    objectName: "menuitem-" + (entry.id ?? "")
    implicitHeight: Metrics.menuItemHeight
    implicitWidth: contentWidth

    Row {
        id: row

        x: Theme.padding.medium ?? 0
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.spacing.medium ?? 0

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            visible: !!root.entry.icon && available
            name: root.entry.icon ?? ""
            color: root.disabled ? root.contentColor : Theme.m3onSurfaceVariant
        }

        Label {
            id: label

            anchors.verticalCenter: parent.verticalCenter
            role: "body.large"
            text: root.entry.text ?? ""
            color: root.contentColor
        }

    }

    Label {
        id: shortcut

        anchors.right: parent.right
        anchors.rightMargin: Theme.padding.medium ?? 0
        anchors.verticalCenter: parent.verticalCenter
        visible: !!root.entry.shortcut
        role: "label.large"
        text: root.entry.shortcut ?? ""
        color: root.disabled ? root.contentColor : Theme.m3onSurfaceVariant
    }

    // The keyboard's current row shows the focus layer.
    StateLayer {
        ripple: false
        disabled: root.disabled
        focused: root.current
        onClicked: root.triggered()
        mouseArea.onContainsMouseChanged: {
            if (mouseArea.containsMouse)
                root.hovered();
        }
    }
}
