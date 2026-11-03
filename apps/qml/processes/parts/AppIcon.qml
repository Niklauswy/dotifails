// The real icon of an app in a container tinted with the icon's own colour mixed into the theme's roles
// (theme-exception: tinte derivado del icono, calculado en ejecución); a letter when the app has no icon.
import QtQuick
import WysunM3

Rectangle {
    id: root

    property string source
    property string tint
    property string label
    property real size: Metrics.iconButtonSize - (Theme.spacing.small ?? 0)
    readonly property color tintColour: tint !== "" ? Qt.color(tint) : Theme.m3secondary

    width: size
    height: size
    radius: Math.round(size * 0.3)
    color: Qt.tint(Theme.m3surfaceContainerHigh, Qt.alpha(tintColour, 0.28))

    Image {
        anchors.centerIn: parent
        width: Math.round(root.size * 0.74)
        height: width
        visible: root.source !== "" && status === Image.Ready
        source: root.source !== "" ? "file://" + root.source : ""
        sourceSize.width: width * 2
        sourceSize.height: height * 2
        asynchronous: true
        smooth: true
    }

    Label {
        anchors.centerIn: parent
        visible: root.source === ""
        text: (root.label || "?").charAt(0).toUpperCase()
        role: root.size > Metrics.iconButtonSize ? "title.large" : "label.large"
        color: Qt.tint(Theme.m3onSurface, Qt.alpha(root.tintColour, 0.45))
    }
}
