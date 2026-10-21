import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.services

// One-line result/progress message under a page's controls.
StyledText {
    property bool error

    Layout.fillWidth: true
    Layout.leftMargin: Tokens.padding.small
    Layout.topMargin: Tokens.spacing.small
    visible: text.length > 0
    wrapMode: Text.Wrap
    color: error ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
    font: Tokens.font.label.medium
}
