// M3 chip, 32 high with the small corner. assist: a smart action next to content (leading icon in primary);
// filter: a toggle that narrows content (selected = secondaryContainer with a check); input: a value the user
// entered (avatar or icon, and a remove button); suggestion: a proposed reply or query.
import QtQuick
import WysunM3

ButtonBase {
    id: root

    property string kind: "assist"          // assist | filter | input | suggestion
    property string text
    property string icon
    property bool selected
    property Component avatar
    readonly property int iconSize: Metrics.chipIconSize
    readonly property string leadingIcon: kind === "filter" && selected ? "check" : icon
    readonly property bool _leadingShown: avatar !== null && kind === "input" || leadingIcon !== ""
    readonly property real _leading: _leadingShown ? Metrics.chipPaddingWithIcon : Metrics.chipPadding
    readonly property real _trailing: kind === "input" ? Metrics.chipPaddingWithIcon : Metrics.chipPadding

    signal removed

    implicitHeight: Metrics.chipHeight
    implicitWidth: _leading + content.implicitWidth + _trailing
    width: implicitWidth
    height: implicitHeight

    morph: false
    restRadius: Theme.rounding.small ?? 0
    checkedRadius: restRadius
    hasContainer: selected
    outline: selected ? 0 : Metrics.outlineWidth
    outlineColor: Theme.m3outlineVariant
    containerColor: Theme.m3secondaryContainer
    contentRestColor: selected ? Theme.m3onSecondaryContainer : kind === "assist" ? Theme.m3onSurface : Theme.m3onSurfaceVariant
    onClicked: {
        if (kind === "filter")
            selected = !selected;
    }

    SpringBehavior on implicitWidth {
        kind: "fastSpatial"
    }

    Row {
        id: content

        x: root._leading
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.spacing.small ?? 0

        Loader {
            anchors.verticalCenter: parent.verticalCenter
            active: root.kind === "input" && root.avatar !== null
            visible: active
            sourceComponent: root.avatar
            width: Metrics.chipAvatarSize
            height: Metrics.chipAvatarSize
        }

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.leadingIcon !== "" && available && !(root.kind === "input" && root.avatar !== null)
            name: root.leadingIcon
            size: root.iconSize
            color: root.kind === "assist" && !root.disabled ? Theme.m3primary : root.contentColor
        }

        Label {
            anchors.verticalCenter: parent.verticalCenter
            role: "label.large"
            text: root.text
            color: root.contentColor
        }

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.kind === "input"
            name: "close"
            size: Metrics.chipIconSize
            color: root.contentColor
        }
    }

    // Input chips: the remove button is its own target, over the chip's state layer.
    MouseArea {
        z: 2
        anchors.right: parent.right
        width: Metrics.chipIconSize + 2 * Metrics.chipPaddingWithIcon
        height: parent.height
        visible: root.kind === "input"
        enabled: !root.disabled
        cursorShape: Qt.PointingHandCursor
        onClicked: root.removed()
    }

    Keys.onDeletePressed: if (kind === "input") removed()
    Keys.onBackPressed: if (kind === "input") removed()
}
