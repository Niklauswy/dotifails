// M3 text field, 56 high. outlined (default; the extraSmall corner, 1 px outline that turns 2 px primary on
// focus) or filled (surfaceContainerHighest with a bottom indicator). The label sits inside and floats up when
// the field has focus or text; supporting/error text goes below. Outlined labels cut the outline with
// `labelBackground`, the colour behind the field.
import QtQuick
import WysunM3

Item {
    id: root

    property string variant: "outlined"      // outlined | filled
    property alias text: input.text
    property string label
    property string placeholder
    property string supportingText
    property bool error
    property string errorText
    property string leadingIcon
    property string trailingIcon
    property alias echoMode: input.echoMode
    property alias readOnly: input.readOnly
    property alias validator: input.validator
    property alias input: input
    property bool disabled
    property color labelBackground: Theme.m3surface

    readonly property bool outlined: variant !== "filled"
    readonly property int fieldHeight: Metrics.textFieldHeight
    readonly property real cornerRadius: Theme.rounding.extraSmall ?? 0
    readonly property bool focused: input.activeFocus
    readonly property bool hovered: hover.hovered && !disabled
    readonly property bool labelFloating: label !== "" && (focused || text !== "" || input.preeditText !== "")
    readonly property int outlineWidth: focused && !disabled ? Metrics.textFieldFocusWidth : Metrics.outlineWidth
    readonly property color indicatorColor: disabled ? Qt.alpha(Theme.m3onSurface, outlined ? Metrics.disabledOutline : Metrics.disabledContent) : error ? Theme.m3error : focused ? Theme.m3primary : hovered ? Theme.m3onSurface : outlined ? Theme.m3outline : Theme.m3onSurfaceVariant
    readonly property color textColor: disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContent) : Theme.m3onSurface
    readonly property color labelColor: disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContent) : error ? Theme.m3error : focused ? Theme.m3primary : Theme.m3onSurfaceVariant
    readonly property string supportingShown: error && errorText !== "" ? errorText : supportingText
    readonly property color supportingColor: disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContent) : error ? Theme.m3error : Theme.m3onSurfaceVariant
    readonly property real labelY: labelText.y
    readonly property bool clipsInput: input.clip
    readonly property string selectedText: input.selectedText
    readonly property real _start: leadingIcon !== "" ? (Theme.padding.medium ?? 0) + Metrics.iconSize + (Theme.padding.large ?? 0) : Theme.padding.large ?? 0
    readonly property real _end: trailingIcon !== "" ? Metrics.iconButtonSize + (Theme.padding.extraSmall ?? 0) : Theme.padding.large ?? 0

    signal accepted
    signal trailingClicked

    function forceFocus() {
        if (!disabled)
            input.forceActiveFocus();
    }
    function insert(position, value) {
        input.insert(position, value);
    }
    function selectAll() {
        input.selectAll();
    }

    implicitWidth: Metrics.textFieldMinWidth
    implicitHeight: fieldHeight + (supportingShown !== "" ? (Theme.padding.extraSmall ?? 0) + supporting.implicitHeight : 0)

    HoverHandler {
        id: hover

        cursorShape: root.disabled ? Qt.ArrowCursor : Qt.IBeamCursor
    }

    Rectangle {
        id: field

        width: parent.width
        height: root.fieldHeight
        radius: root.outlined ? root.cornerRadius : 0
        topLeftRadius: root.cornerRadius
        topRightRadius: root.cornerRadius
        color: root.outlined ? "transparent" : root.disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledFilledField) : Theme.m3surfaceContainerHighest
        border.width: root.outlined ? root.outlineWidth : 0
        border.color: root.indicatorColor

        Behavior on border.color {
            CAnim {
                kind: "fastEffects"
            }
        }

        // Filled: the active indicator along the bottom edge.
        Rectangle {
            visible: !root.outlined
            anchors.bottom: parent.bottom
            width: parent.width
            height: root.outlineWidth
            color: root.indicatorColor
        }

        // Filled: the hover state layer.
        Rectangle {
            visible: !root.outlined
            anchors.fill: parent
            topLeftRadius: root.cornerRadius
            topRightRadius: root.cornerRadius
            color: Theme.m3onSurface
            opacity: root.hovered && !root.focused ? Metrics.stateHover : 0
        }

        MouseArea {
            anchors.fill: parent
            enabled: !root.disabled
            cursorShape: Qt.IBeamCursor
            onPressed: root.forceFocus()
        }

        Icon {
            x: Theme.padding.medium ?? 0
            anchors.verticalCenter: parent.verticalCenter
            visible: root.leadingIcon !== "" && available
            name: root.leadingIcon
            color: root.disabled ? root.textColor : Theme.m3onSurfaceVariant
        }

        TextInput {
            id: input

            readonly property var type: Theme.typeFont("body.large")

            x: root._start
            width: parent.width - root._start - root._end
            y: !root.outlined && root.label !== "" ? parent.height - height - (Theme.padding.small ?? 0) : (parent.height - height) / 2
            clip: true
            enabled: !root.disabled
            color: root.textColor
            selectionColor: Theme.m3primary
            selectedTextColor: Theme.m3onPrimary
            selectByMouse: true
            activeFocusOnTab: !root.disabled
            font.family: type.family
            font.pointSize: type.pointSize > 0 ? type.pointSize : Qt.application.font.pointSize
            font.weight: type.weight
            renderType: Text.NativeRendering
            onAccepted: root.accepted()
        }

        Label {
            x: input.x
            y: input.y
            visible: root.text === "" && input.preeditText === "" && (root.labelFloating || root.label === "")
            role: "body.large"
            text: root.placeholder
            color: root.disabled ? root.textColor : Theme.m3onSurfaceVariant
        }

        // Outlined: the floating label interrupts the outline.
        Rectangle {
            visible: root.outlined && root.labelFloating
            x: labelText.x - (Theme.padding.extraSmall ?? 0)
            y: labelText.y
            width: labelText.width + 2 * (Theme.padding.extraSmall ?? 0)
            height: labelText.height
            color: root.labelBackground
        }

        Label {
            id: labelText

            x: root.labelFloating && root.outlined ? Theme.padding.large ?? 0 : root._start
            y: root.labelFloating ? (root.outlined ? -height / 2 : Theme.padding.small ?? 0) : (parent.height - height) / 2
            visible: root.label !== ""
            role: root.labelFloating ? "body.small" : "body.large"
            text: root.label
            color: root.labelColor

            SpringBehavior on y {
                kind: "fastSpatial"
            }
            SpringBehavior on x {
                kind: "fastSpatial"
            }
        }

        IconButton {
            anchors.right: parent.right
            anchors.rightMargin: Theme.padding.extraSmall ?? 0
            anchors.verticalCenter: parent.verticalCenter
            visible: root.trailingIcon !== ""
            icon: root.trailingIcon
            disabled: root.disabled
            onClicked: root.trailingClicked()
        }
    }

    Label {
        id: supporting

        x: Theme.padding.large ?? 0
        y: root.fieldHeight + (Theme.padding.extraSmall ?? 0)
        width: parent.width - 2 * (Theme.padding.large ?? 0)
        visible: root.supportingShown !== ""
        role: "body.small"
        text: root.supportingShown
        color: root.supportingColor
        elide: Text.ElideRight
    }
}
