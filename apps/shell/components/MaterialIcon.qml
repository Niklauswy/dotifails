import QtQuick
import "../" as Wysun

Text {
    id: root
    property string name: "circle"
    property int size: 20
    Accessible.ignored: true
    text: name
    color: Wysun.Appearance.text
    font.family: Wysun.Appearance.iconFontFamily
    font.pixelSize: size
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    renderType: Text.NativeRendering
}
