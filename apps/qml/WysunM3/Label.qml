// Text in an M3 type role ("headline|title|body|label" . "large|medium|small"), coloured from the theme.
import QtQuick

Text {
    id: root

    property string role: "body.medium"
    readonly property var type: Theme.typeFont(role)

    color: Theme.m3onSurface
    font.family: type.family
    font.pointSize: type.pointSize > 0 ? type.pointSize : Qt.application.font.pointSize
    font.weight: type.weight
    renderType: Text.NativeRendering
    textFormat: Text.PlainText
}
