pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes
import Wysun.Config
import qs.components
import qs.services

// A light that runs once around a rounded rectangle, starting at the top centre: the study mode signature.
// Bump `tick` to run it; `quick` makes a quicker, fainter lap.
Item {
    id: root

    property int tick
    property bool quick
    property real radius
    property real line: Tokens.padding.extraSmall - 1
    readonly property real perimeter: 2 * (width + height) - (8 - 2 * Math.PI) * Math.min(radius, width / 2, height / 2)
    // Length of the travelling light, along the edge.
    readonly property real trail: perimeter * 0.22
    property real travelled: 0

    onTickChanged: {
        if (width > 0 && height > 0)
            run.restart();
    }

    opacity: 0

    SequentialAnimation {
        id: run

        PropertyAction {
            target: root
            property: "travelled"
            value: 0
        }
        ParallelAnimation {
            Anim {
                target: root
                property: "travelled"
                to: root.perimeter + root.trail
                duration: root.quick ? Tokens.anim.durations.extraLarge : Tokens.anim.durations.extraLarge + Tokens.anim.durations.large
                easing: Tokens.anim.emphasized
            }
            SequentialAnimation {
                Anim {
                    target: root
                    property: "opacity"
                    to: root.quick ? 0.6 : 1
                    type: Anim.FastEffects
                }
                PauseAnimation {
                    duration: root.quick ? Tokens.anim.durations.normal : Tokens.anim.durations.extraLarge
                }
                Anim {
                    target: root
                    property: "opacity"
                    to: 0
                    type: Anim.SlowEffects
                }
            }
        }
    }

    Repeater {
        // A soft wide glow under a thin bright line.
        model: [3, 1]

        Shape {
            id: shape

            required property int modelData
            required property int index

            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            opacity: index === 0 ? 0.35 : 1

            ShapePath {
                strokeColor: shape.index === 0 ? Colours.palette.m3primary : Colours.palette.m3tertiary
                strokeWidth: root.line * shape.modelData
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                strokeStyle: ShapePath.DashLine
                // Dash units are stroke widths: one dash as long as the trail, then a gap of a whole lap.
                dashPattern: [root.trail / strokeWidth, root.perimeter / strokeWidth]
                // Path starts at the top-left corner: shift so the light starts at the top centre.
                dashOffset: (root.trail - root.travelled - root.width / 2) / strokeWidth

                PathRectangle {
                    x: root.line * shape.modelData / 2
                    y: root.line * shape.modelData / 2
                    width: root.width - root.line * shape.modelData
                    height: root.height - root.line * shape.modelData
                    radius: root.radius
                }
            }
        }
    }
}
