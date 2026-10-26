// The M3 state layer of an interactive surface: 8 % hover, 12 % focus, 12 % pressed, 16 % dragged of `tint`
// (the strongest one shows, they never stack), plus an optional ripple from the press point that the shell's
// StateLayer also has. Put it inside the control, last, so it paints over the background and under nothing.
import QtQuick
import QtQuick.Shapes

Item {
    id: root

    property color tint: Theme.m3onSurface
    property real radius: 0
    property bool disabled
    property bool focused               // keyboard focus, set by the owner
    property bool dragged
    property bool ripple: true
    readonly property bool hovered: area.containsMouse && !disabled
    readonly property bool pressed: area.pressed && !disabled
    readonly property alias mouseArea: area

    signal clicked(var mouse)
    signal pressAndHold(var mouse)

    readonly property real baseOpacity: disabled ? 0 : dragged ? Theme.stateOpacity("dragged") : focused ? Theme.stateOpacity("focus") : hovered ? Theme.stateOpacity("hover") : 0
    readonly property real layerOpacity: Math.max(baseOpacity, pressed && !ripple && !disabled ? Theme.stateOpacity("pressed") : 0)
    // The ripple completes the base layer to the pressed opacity: 1 - (1 - pressed) / (1 - base).
    readonly property real rippleOpacity: Math.max(0, 1 - (1 - Theme.stateOpacity("pressed")) / (1 - baseOpacity))

    property real _pressX: width / 2
    property real _pressY: height / 2
    property real _circleRadius: 0
    readonly property real _endRadius: {
        const dx = Math.max(_pressX, width - _pressX);
        const dy = Math.max(_pressY, height - _pressY);
        return Math.sqrt(dx * dx + dy * dy) * 1.05;
    }
    readonly property real _r: Math.max(0, Math.min(radius, width / 2, height / 2))

    anchors.fill: parent

    Rectangle {
        anchors.fill: parent
        radius: root.radius
        color: root.tint
        opacity: root.layerOpacity

        SpringBehavior on opacity {
            kind: "fastEffects"
        }
    }

    Shape {
        id: wave

        anchors.fill: parent
        visible: root.ripple
        opacity: 0
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeWidth: 0
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: root._pressX
                centerY: root._pressY
                centerRadius: Math.max(0.01, root._circleRadius)
                focalX: centerX
                focalY: centerY

                GradientStop {
                    position: 0
                    color: root.tint
                }
                GradientStop {
                    position: 0.97
                    color: root.tint
                }
                GradientStop {
                    position: 1
                    color: Qt.alpha(root.tint, 0)
                }
            }

            startX: root._r
            startY: 0
            PathLine {
                x: root.width - root._r
                y: 0
            }
            PathArc {
                x: root.width
                y: root._r
                radiusX: root._r
                radiusY: root._r
            }
            PathLine {
                x: root.width
                y: root.height - root._r
            }
            PathArc {
                x: root.width - root._r
                y: root.height
                radiusX: root._r
                radiusY: root._r
            }
            PathLine {
                x: root._r
                y: root.height
            }
            PathArc {
                x: 0
                y: root.height - root._r
                radiusX: root._r
                radiusY: root._r
            }
            PathLine {
                x: 0
                y: root._r
            }
            PathArc {
                x: root._r
                y: 0
                radiusX: root._r
                radiusY: root._r
            }
        }
    }

    Anim {
        id: grow

        target: root
        property: "_circleRadius"
        from: 0
        to: root._endRadius
        kind: "slowEffects"
        onRunningChanged: {
            if (!running && !area.pressed)
                fade.restart();
        }
    }

    Anim {
        id: fade

        target: wave
        property: "opacity"
        to: 0
        kind: "slowEffects"
    }

    MouseArea {
        id: area

        anchors.fill: parent
        enabled: !root.disabled
        hoverEnabled: true
        cursorShape: root.disabled ? Qt.ArrowCursor : Qt.PointingHandCursor
        onPressed: mouse => {
            if (!root.ripple)
                return;
            root._pressX = mouse.x;
            root._pressY = mouse.y;
            fade.stop();
            wave.opacity = root.rippleOpacity;
            grow.restart();
        }
        onReleased: {
            if (root.ripple && !grow.running)
                fade.restart();
        }
        onCanceled: {
            if (root.ripple && !grow.running)
                fade.restart();
        }
        onClicked: mouse => root.clicked(mouse)
        onPressAndHold: mouse => root.pressAndHold(mouse)
    }
}
