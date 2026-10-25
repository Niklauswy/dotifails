// Wysun's own mark for the terminal: a globe of ellipses with the name across it (not Lumon's).
import QtQuick
import QtQuick.Shapes

Item {
    id: markItem

    property color colour
    property color fill
    property real stroke: 1
    property real spin: 0
    property string family: "monospace"

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: markItem.colour
            strokeWidth: markItem.stroke
            fillColor: markItem.fill
            PathAngleArc {
                centerX: markItem.width / 2
                centerY: markItem.height / 2
                radiusX: markItem.width / 2 - markItem.stroke
                radiusY: markItem.height / 2 - markItem.stroke
                startAngle: 0
                sweepAngle: 360
            }
        }
        ShapePath {
            strokeColor: markItem.colour
            strokeWidth: markItem.stroke
            fillColor: "transparent"
            PathAngleArc {
                centerX: markItem.width / 2
                centerY: markItem.height / 2
                radiusX: markItem.width * 0.28 * Math.abs(Math.cos(markItem.spin * 0.4))
                radiusY: markItem.height / 2 - markItem.stroke
                startAngle: 0
                sweepAngle: 360
            }
        }
        ShapePath {
            strokeColor: markItem.colour
            strokeWidth: markItem.stroke
            fillColor: "transparent"
            PathAngleArc {
                centerX: markItem.width / 2
                centerY: markItem.height / 2
                radiusX: markItem.width / 2 - markItem.stroke
                radiusY: markItem.height * 0.22
                startAngle: 0
                sweepAngle: 360
            }
        }
    }
    Rectangle {
        anchors.centerIn: parent
        width: markText.implicitWidth + markItem.height * 0.3
        height: markText.implicitHeight
        color: markItem.fill
    }
    Text {
        id: markText
        anchors.centerIn: parent
        text: "WYSUN"
        color: markItem.colour
        font.family: markItem.family
        font.pixelSize: markItem.height * 0.26
        font.letterSpacing: markItem.height * 0.06
        font.bold: true
    }
}
