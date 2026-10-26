// The M3Shapes-backed body of ShapeEmblem, loaded on its own so a runtime without M3Shapes only fails this file.
import QtQuick
import M3Shapes

MaterialShape {
    property string shapeName: "Cookie9Sided"
    property string hoverShapeName: shapeName
    property bool hovered

    objectName: "emblemShape"
    implicitSize: Math.min(width, height)
    shape: MaterialShape[hovered ? hoverShapeName : shapeName]
}
