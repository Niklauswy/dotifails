// M3 common button: filled (most important action), tonal (secondary emphasis), outlined (medium), text (lowest)
// and elevated (when it must stand out from a tinted background). 40 high, label-large, optional 18 px icon.
// `checkable` makes it a toggle: checked uses the stronger colours and the squarer checked corner.
import QtQuick
import WysunM3

ButtonBase {
    id: root

    property string type: "filled"           // filled | tonal | outlined | text | elevated
    property string text
    property string icon
    readonly property int iconSize: Metrics.buttonIconSize
    readonly property real _leading: type === "text" ? Metrics.textButtonPadding : icon !== "" ? Metrics.buttonPaddingWithIcon : Metrics.buttonPadding
    readonly property real _trailing: type === "text" ? Metrics.textButtonPadding : Metrics.buttonPadding

    implicitHeight: Metrics.buttonHeight
    implicitWidth: _leading + content.implicitWidth + _trailing
    width: implicitWidth
    height: implicitHeight

    hasContainer: type !== "text" && type !== "outlined"
    elevation: type === "elevated" ? 1 : 0
    outline: type === "outlined" ? Metrics.outlineWidth : 0
    outlineColor: Theme.m3outline
    containerColor: {
        switch (type) {
        case "filled":
            return checkable && !checked ? Theme.m3surfaceContainer : Theme.m3primary;
        case "tonal":
            return checkable && checked ? Theme.m3secondary : Theme.m3secondaryContainer;
        case "elevated":
            return checkable && checked ? Theme.m3primary : Theme.m3surfaceContainerLow;
        }
        return "transparent";
    }
    contentRestColor: {
        switch (type) {
        case "filled":
            return checkable && !checked ? Theme.m3onSurfaceVariant : Theme.m3onPrimary;
        case "tonal":
            return checkable && checked ? Theme.m3onSecondary : Theme.m3onSecondaryContainer;
        case "elevated":
            return checkable && checked ? Theme.m3onPrimary : Theme.m3primary;
        }
        return Theme.m3primary;
    }

    readonly property real contentX: content.x

    Row {
        id: content

        // Centred when the button is wider than its content.
        x: Math.max(root._leading, (root.width - content.implicitWidth) / 2)
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.spacing.small ?? 0

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.icon !== "" && available
            name: root.icon
            size: root.iconSize
            filled: root.checkable && root.checked
            color: root.contentColor
        }

        Label {
            anchors.verticalCenter: parent.verticalCenter
            role: "label.large"
            text: root.text
            color: root.contentColor
        }
    }
}
