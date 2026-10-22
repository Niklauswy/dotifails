pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes
import Wysun.Config
import qs.components
import qs.services

// The selection hangs from four strings tied to the output corners. With no
// region the four nodes meet under the pointer; while selecting they sit on the
// region corners. Nodes follow on a stiff spring and the strings bend on a
// looser one, so they swing as the selection moves.
Item {
    id: root

    // Target corners of the selection (tl, tr, bl, br); equal points for one node.
    property point tl
    property point tr
    property point bl
    property point br
    property bool single: true
    property bool outline: !single
    property color colour: Colours.palette.m3primary

    // Springy region the dim mask and outline follow.
    readonly property rect shown: Qt.rect(Math.min(n0.x, n2.x), Math.min(n0.y, n1.y), Math.max(n1.x, n3.x) - Math.min(n0.x, n2.x), Math.max(n2.y, n3.y) - Math.min(n0.y, n1.y))

    // Jump straight to the targets, e.g. when the pointer enters this output.
    function settle(): void {
        for (const p of [n0, n1, n2, n3, l0, l1, l2, l3])
            p.snap();
    }

    SpringPoint {
        id: n0

        target: root.tl
    }

    SpringPoint {
        id: n1

        target: root.tr
    }

    SpringPoint {
        id: n2

        target: root.bl
    }

    SpringPoint {
        id: n3

        target: root.br
    }

    SpringPoint {
        id: l0

        target: root.tl
        spring: Tokens.sizes.screenshot.stringSpring
        damping: Tokens.sizes.screenshot.stringDamping
    }

    SpringPoint {
        id: l1

        target: root.tr
        spring: Tokens.sizes.screenshot.stringSpring
        damping: Tokens.sizes.screenshot.stringDamping
    }

    SpringPoint {
        id: l2

        target: root.bl
        spring: Tokens.sizes.screenshot.stringSpring
        damping: Tokens.sizes.screenshot.stringDamping
    }

    SpringPoint {
        id: l3

        target: root.br
        spring: Tokens.sizes.screenshot.stringSpring
        damping: Tokens.sizes.screenshot.stringDamping
    }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        Rope {
            cornerX: 0
            cornerY: 0
            node: n0
            lag: l0
        }

        Rope {
            cornerX: root.width
            cornerY: 0
            node: n1
            lag: l1
        }

        Rope {
            cornerX: 0
            cornerY: root.height
            node: n2
            lag: l2
        }

        Rope {
            cornerX: root.width
            cornerY: root.height
            node: n3
            lag: l3
        }

        // Region outline through the four nodes.
        ShapePath {
            strokeColor: root.outline ? root.colour : "transparent"
            strokeWidth: Tokens.sizes.screenshot.outlineWidth
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin

            PathPolyline {
                path: [Qt.point(n0.x, n0.y), Qt.point(n1.x, n1.y), Qt.point(n3.x, n3.y), Qt.point(n2.x, n2.y), Qt.point(n0.x, n0.y)]
            }
        }
    }

    Repeater {
        model: root.single ? [n0] : [n0, n1, n2, n3]

        StyledRect {
            required property Item modelData

            x: modelData.x - width / 2
            y: modelData.y - height / 2
            implicitWidth: Tokens.sizes.screenshot.nodeSize
            implicitHeight: implicitWidth
            radius: Tokens.rounding.full
            color: root.colour
            border.width: Tokens.sizes.screenshot.outlineWidth
            border.color: Qt.alpha(Colours.palette.m3surface, 0.6)
        }
    }

    component SpringPoint: Item {
        id: point

        property point target
        property real spring: Tokens.sizes.screenshot.nodeSpring
        property real damping: Tokens.sizes.screenshot.nodeDamping

        function snap(): void {
            bx.enabled = by.enabled = false;
            x = target.x;
            y = target.y;
            bx.enabled = by.enabled = true;
        }

        x: target.x
        y: target.y

        Behavior on x {
            id: bx

            SpringAnimation {
                spring: point.spring
                damping: point.damping
                epsilon: 0.25
            }
        }

        Behavior on y {
            id: by

            SpringAnimation {
                spring: point.spring
                damping: point.damping
                epsilon: 0.25
            }
        }
    }

    component Rope: ShapePath {
        id: rope

        required property real cornerX
        required property real cornerY
        required property Item node
        required property Item lag

        readonly property real sag: Tokens.sizes.screenshot.stringSag

        strokeColor: root.colour
        strokeWidth: Tokens.sizes.screenshot.stringWidth
        fillColor: "transparent"
        capStyle: ShapePath.RoundCap
        startX: cornerX
        startY: cornerY

        // Leaves the corner towards the node, arrives level with it.
        PathCubic {
            control1X: rope.cornerX + (rope.lag.x - rope.cornerX) * (1 - rope.sag) * 0.6
            control1Y: rope.cornerY + (rope.lag.y - rope.cornerY) * rope.sag * 1.2
            control2X: rope.lag.x + (rope.cornerX - rope.lag.x) * rope.sag
            control2Y: rope.lag.y
            x: rope.node.x
            y: rope.node.y
        }
    }
}
