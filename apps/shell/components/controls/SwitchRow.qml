import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components

// A label and its switch, filling the row of a popout.
RowLayout {
    id: root

    required property string label
    property alias checked: toggle.checked
    property alias toggle: toggle

    Layout.fillWidth: true
    Layout.rightMargin: Tokens.padding.extraSmall
    spacing: Tokens.spacing.medium

    StyledText {
        Layout.fillWidth: true
        text: root.label
    }

    StyledSwitch {
        id: toggle
    }
}
