// Wysun's globe for the training card: heavy strokes, two latitudes framing a band with the name.
// The same mark as the terminal's WysunMark, drawn the way a title card would print it.
import QtQuick
import QtQuick.Shapes

Item {
    id: mark

    property color colour
    property color fill
    property string family: "sans-serif"
    readonly property real stroke: height * 0.04
    readonly property real band: height * 0.165

    function chord(y: real): real {
        const ry = height / 2 - stroke / 2;
        return (width / 2 - stroke / 2) * Math.sqrt(Math.max(0, 1 - (y * y) / (ry * ry)));
    }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        // Meridians first: the band covers them where the name sits.
        ShapePath {
            strokeColor: mark.colour
            strokeWidth: mark.stroke
            fillColor: "transparent"
            PathAngleArc {
                centerX: mark.width / 2
                centerY: mark.height / 2
                radiusX: mark.width * 0.27
                radiusY: mark.height / 2 - mark.stroke / 2
                startAngle: 0
                sweepAngle: 360
            }
        }
        ShapePath {
            strokeColor: mark.colour
            strokeWidth: mark.stroke
            fillColor: "transparent"
            startX: mark.width / 2 - mark.chord(-mark.height * 0.3)
            startY: mark.height * 0.2
            PathLine { x: mark.width / 2 + mark.chord(-mark.height * 0.3); y: mark.height * 0.2 }
            PathMove { x: mark.width / 2 - mark.chord(mark.height * 0.3); y: mark.height * 0.8 }
            PathLine { x: mark.width / 2 + mark.chord(mark.height * 0.3); y: mark.height * 0.8 }
        }
    }

    Rectangle {
        x: mark.width / 2 - mark.chord(mark.band)
        y: mark.height / 2 - mark.band
        width: mark.chord(mark.band) * 2
        height: mark.band * 2
        color: mark.fill
    }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: mark.colour
            strokeWidth: mark.stroke
            fillColor: "transparent"
            PathAngleArc {
                centerX: mark.width / 2
                centerY: mark.height / 2
                radiusX: mark.width / 2 - mark.stroke / 2
                radiusY: mark.height / 2 - mark.stroke / 2
                startAngle: 0
                sweepAngle: 360
            }
        }
        ShapePath {
            strokeColor: mark.colour
            strokeWidth: mark.stroke
            fillColor: "transparent"
            startX: mark.width / 2 - mark.chord(-mark.band)
            startY: mark.height / 2 - mark.band
            PathLine { x: mark.width / 2 + mark.chord(-mark.band); y: mark.height / 2 - mark.band }
            PathMove { x: mark.width / 2 - mark.chord(mark.band); y: mark.height / 2 + mark.band }
            PathLine { x: mark.width / 2 + mark.chord(mark.band); y: mark.height / 2 + mark.band }
        }
    }

    Text {
        anchors.centerIn: parent
        text: "WYSUN"
        color: mark.colour
        font.family: mark.family
        font.pixelSize: mark.height * 0.24
        font.weight: Font.Black
        font.letterSpacing: mark.height * 0.02
    }
}
