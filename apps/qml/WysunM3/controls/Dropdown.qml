// M3 exposed dropdown (outlined): a 56 high field that shows the current choice and opens a Menu below it.
// model: [{value, text}]; `current` is the value shown. Choosing a row sets `current` and emits activated(value).
// Click, Space or Enter open it (↑/↓ too); the menu starts on the current row and Escape closes it unchanged.
import QtQuick
import WysunM3

ButtonBase {
    id: root

    property var model: []
    property string current
    property string placeholder
    readonly property string currentText: {
        for (const option of model)
            if (option.value === current)
                return option.text;
        return "";
    }
    readonly property string displayText: currentText !== "" ? currentText : placeholder
    readonly property bool opened: menu.opened

    signal activated(string value)

    function open() {
        if (disabled || opened || model.length === 0)
            return;
        menu.popup(root, 0, root.height);
        for (let i = 0; i < model.length; ++i) {
            if (model[i].value === current) {
                menu.currentIndex = i;
                break;
            }
        }
    }

    implicitWidth: Metrics.textFieldMinWidth
    implicitHeight: Metrics.textFieldHeight
    width: implicitWidth
    height: implicitHeight
    morph: false
    hasContainer: false
    restRadius: Theme.rounding.extraSmall ?? 0
    contentRestColor: Theme.m3onSurface
    outline: Metrics.outlineWidth
    outlineColor: opened ? Theme.m3primary : hovered ? Theme.m3onSurface : Theme.m3outline
    onClicked: open()
    Keys.onDownPressed: event => {
        open();
        event.accepted = true;
    }
    Keys.onUpPressed: event => {
        open();
        event.accepted = true;
    }

    Label {
        anchors.left: parent.left
        anchors.leftMargin: Theme.padding.large ?? 0
        anchors.right: arrow.left
        anchors.rightMargin: Theme.padding.small ?? 0
        anchors.verticalCenter: parent.verticalCenter
        role: "body.large"
        elide: Text.ElideRight
        text: root.displayText
        color: root.disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContent) : root.currentText !== "" ? Theme.m3onSurface : Theme.m3onSurfaceVariant
    }

    Icon {
        id: arrow

        anchors.right: parent.right
        anchors.rightMargin: Theme.padding.medium ?? 0
        anchors.verticalCenter: parent.verticalCenter
        name: "arrow_drop_down"
        color: root.disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContent) : Theme.m3onSurfaceVariant
        rotation: root.opened ? 180 : 0

        SpringBehavior on rotation {
            kind: "fastSpatial"
        }
    }

    Menu {
        id: menu

        objectName: "dropdownMenu"
        model: root.model.map(option => ({
                    id: option.value,
                    text: option.text
                }))
        onTriggered: id => {
            root.current = id;
            root.activated(id);
        }
    }
}
