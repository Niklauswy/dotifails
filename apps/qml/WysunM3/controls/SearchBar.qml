// M3 search bar: 56 high, full corner, surfaceContainerHigh, body-large text. A clear button appears with text;
// Escape clears it (and passes through when it is already empty), Enter emits `accepted`. Ctrl+L (`shortcut`)
// or forceFocus() put the caret in it. `trailing` adds icons after the clear button (e.g. an avatar or filters).
import QtQuick
import WysunM3

Rectangle {
    id: root

    property alias text: input.text
    property string placeholder
    property string leadingIcon: "search"
    property Component trailing
    property string shortcut: "Ctrl+L"
    property alias input: input
    readonly property bool clearVisible: text !== ""
    readonly property bool focused: input.activeFocus

    signal accepted
    signal cleared

    function forceFocus() {
        input.forceActiveFocus();
    }
    function clear() {
        if (input.text === "")
            return;
        input.text = "";
        cleared();
    }

    implicitWidth: Metrics.textFieldMinWidth
    implicitHeight: Metrics.searchBarHeight
    height: implicitHeight
    radius: Theme.fullRadius(height)
    color: Theme.m3surfaceContainerHigh

    Shortcut {
        sequence: root.shortcut
        enabled: root.shortcut !== "" && root.visible
        onActivated: root.forceFocus()
    }

    StateLayer {
        radius: root.radius
        ripple: false
        tint: Theme.m3onSurface
        onClicked: root.forceFocus()
    }

    Icon {
        id: lead

        x: Theme.padding.large ?? 0
        anchors.verticalCenter: parent.verticalCenter
        name: root.leadingIcon
        color: Theme.m3onSurface
    }

    TextInput {
        id: input

        readonly property var type: Theme.typeFont("body.large")

        x: lead.x + lead.width + (Theme.padding.large ?? 0)
        width: tail.x - x - (Theme.padding.small ?? 0)
        anchors.verticalCenter: parent.verticalCenter
        clip: true
        color: Theme.m3onSurface
        selectionColor: Theme.m3primary
        selectedTextColor: Theme.m3onPrimary
        selectByMouse: true
        font.family: type.family
        font.pointSize: type.pointSize > 0 ? type.pointSize : Qt.application.font.pointSize
        font.weight: type.weight
        renderType: Text.NativeRendering
        onAccepted: root.accepted()
        Keys.onEscapePressed: event => {
            if (text === "") {
                event.accepted = false;
                return;
            }
            root.clear();
        }
    }

    Label {
        anchors.verticalCenter: parent.verticalCenter
        x: input.x
        visible: root.text === "" && input.preeditText === ""
        role: "body.large"
        text: root.placeholder
        color: Theme.m3onSurfaceVariant
    }

    Row {
        id: tail

        anchors.right: parent.right
        anchors.rightMargin: Theme.padding.small ?? 0
        anchors.verticalCenter: parent.verticalCenter

        IconButton {
            visible: root.clearVisible
            icon: "close"
            onClicked: {
                root.clear();
                root.forceFocus();
            }
        }

        Loader {
            anchors.verticalCenter: parent.verticalCenter
            sourceComponent: root.trailing
            active: root.trailing !== null
        }
    }
}
