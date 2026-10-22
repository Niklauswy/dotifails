import QtQuick
import QtQuick.Shapes
import Wysun.Config
import qs.components
import qs.services
import "Logos.js" as Logos

// Official provider marks (Logos.js) drawn as vectors in the theme colour.
Item {
    id: root

    // Provider id or a key of Logos.paths ("claude", "codex", "gemini", ...).
    property string provider
    property color colour: Colours.palette.m3onSurface
    property real size: Tokens.spacing.largeIncreased

    readonly property string path: Logos.paths[provider] ?? ""

    implicitWidth: size
    implicitHeight: size

    Shape {
        anchors.centerIn: parent
        width: 24
        height: 24
        scale: root.size / 24
        visible: root.path.length > 0
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            fillColor: root.colour
            fillRule: ShapePath.OddEvenFill
            strokeColor: "transparent"
            strokeWidth: 0

            PathSvg {
                path: root.path
            }
        }
    }

    MaterialIcon {
        anchors.centerIn: parent
        visible: root.path.length === 0
        text: "smart_toy"
        color: root.colour
    }
}
