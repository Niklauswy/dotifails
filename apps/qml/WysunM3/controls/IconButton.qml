// M3 icon button (40 target, 24 icon): standard for low emphasis in toolbars, filled/tonal for the main or a
// secondary action, outlined for medium emphasis. `checkable` toggles it; `iconChecked` replaces the icon then,
// which is drawn filled.
import QtQuick
import WysunM3

ButtonBase {
    id: root

    property string type: "standard"         // standard | filled | tonal | outlined
    property string icon
    property string iconChecked
    property real iconSize: Metrics.iconSize
    readonly property string shownIcon: checkable && checked && iconChecked !== "" ? iconChecked : icon

    implicitWidth: Metrics.iconButtonSize
    implicitHeight: Metrics.iconButtonSize
    width: implicitWidth
    height: implicitHeight

    hasContainer: type === "filled" || type === "tonal" || (type === "outlined" && checkable && checked)
    outline: type === "outlined" && !(checkable && checked) ? Metrics.outlineWidth : 0
    outlineColor: Theme.m3outlineVariant
    containerColor: {
        switch (type) {
        case "filled":
            return checkable && !checked ? Theme.m3surfaceContainerHighest : Theme.m3primary;
        case "tonal":
            return checkable && checked ? Theme.m3secondary : Theme.m3secondaryContainer;
        case "outlined":
            return Theme.m3inverseSurface;
        }
        return "transparent";
    }
    contentRestColor: {
        switch (type) {
        case "filled":
            return checkable && !checked ? Theme.m3primary : Theme.m3onPrimary;
        case "tonal":
            return checkable && checked ? Theme.m3onSecondary : Theme.m3onSecondaryContainer;
        case "outlined":
            return checkable && checked ? Theme.m3inverseOnSurface : Theme.m3onSurfaceVariant;
        }
        return checkable && checked ? Theme.m3primary : Theme.m3onSurfaceVariant;
    }

    Icon {
        anchors.centerIn: parent
        name: root.shownIcon
        size: root.iconSize
        filled: root.checkable && root.checked
        color: root.contentColor
    }
}
