// A Material Symbols Rounded glyph by ligature name. If the icon font is not available nothing is drawn: the
// ligature name must never show up as plain text.
import QtQuick

Text {
    id: root

    property string name
    property bool filled
    property real size: Metrics.iconSize
    readonly property bool available: Theme.fontAvailable(Theme.iconFamily)

    width: size
    height: size
    visible: available && name !== ""
    text: available ? name : ""
    color: Theme.m3onSurface
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    renderType: Text.NativeRendering
    font.family: Theme.iconFamily
    font.pixelSize: size
    font.variableAxes: ({
            "FILL": filled ? 1 : 0,
            "GRAD": Theme.dark ? -25 : 0,
            "opsz": Math.max(20, Math.min(48, size))
        })
}
