import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services

// Back button and title of a sub-page, with room for controls on the right.
RowLayout {
    id: root

    property string title
    default property alias controls: extra.data

    signal backRequested

    Layout.fillWidth: true
    spacing: Tokens.spacing.small

    IconButton {
        icon: "arrow_back"
        type: IconButton.Text
        onClicked: root.backRequested()
    }

    StyledText {
        Layout.fillWidth: true
        text: root.title
        font: Tokens.font.title.medium
        elide: Text.ElideRight
    }

    RowLayout {
        id: extra

        spacing: Tokens.spacing.small
    }
}
