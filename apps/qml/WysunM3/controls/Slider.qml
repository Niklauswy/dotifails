// M3 slider: a primary active track up to the value, a gap, the secondaryContainer inactive track and a 20 px
// handle; a 40 px target. `wavy` turns the active track into the M3 Expressive wave (song progress), which
// travels while `waveMoving` (stops with reduced motion). ←/→ change by `stepSize`, PgUp/PgDn by `pageStep`,
// Home/End jump to the ends. While dragging, `value` follows the pointer and `moved(value)` reports it; set
// `live: false` to report only on release (`released(value)`).
import QtQuick
import QtQuick.Shapes
import WysunM3

Item {
    id: root

    property real from: 0
    property real to: 1
    property real value: 0
    property real stepSize: (to - from) / 20
    property real pageStep: (to - from) / 5
    property bool live: true
    property bool wavy
    property bool waveMoving
    property bool disabled
    readonly property bool pressed: area.pressed
    readonly property real position: to > from ? Math.max(0, Math.min(1, (value - from) / (to - from))) : 0
    readonly property real handleX: _track * position
    readonly property real _track: Math.max(0, width - Metrics.sliderHandle)
    property real _phase: 0
    property bool _dragging

    signal moved(real value)
    signal released(real value)

    function _set(v) {
        const clamped = Math.max(from, Math.min(to, v));
        if (clamped === value)
            return;
        value = clamped;
        if (live || !_dragging)
            moved(clamped);
    }

    implicitWidth: Metrics.textFieldMinWidth
    implicitHeight: Metrics.sliderTarget
    focusPolicy: disabled ? Qt.NoFocus : Qt.TabFocus
    activeFocusOnTab: !disabled
    opacity: disabled ? Metrics.disabledContent : 1

    Keys.onPressed: event => {
        const delta = {
            [Qt.Key_Left]: -stepSize,
            [Qt.Key_Down]: -stepSize,
            [Qt.Key_Right]: stepSize,
            [Qt.Key_Up]: stepSize,
            [Qt.Key_PageDown]: -pageStep,
            [Qt.Key_PageUp]: pageStep
        }[event.key];
        if (delta !== undefined)
            _set(value + delta);
        else if (event.key === Qt.Key_Home)
            _set(from);
        else if (event.key === Qt.Key_End)
            _set(to);
        else
            return;
        event.accepted = true;
    }

    Item {
        id: track

        x: Metrics.sliderHandle / 2
        width: root._track
        height: parent.height

        // Inactive track after the handle (a gap either side of it).
        Rectangle {
            x: root.handleX + Metrics.sliderHandle / 2 + Metrics.progressGap
            width: Math.max(0, track.width - x)
            anchors.verticalCenter: parent.verticalCenter
            height: Metrics.sliderTrack
            radius: height / 2
            color: Theme.m3secondaryContainer
        }

        Rectangle {
            visible: !root.wavy
            width: Math.max(0, root.handleX - Metrics.sliderHandle / 2 - Metrics.progressGap)
            anchors.verticalCenter: parent.verticalCenter
            height: Metrics.sliderTrack
            radius: height / 2
            color: Theme.m3primary
        }

        Shape {
            visible: root.wavy
            width: Math.max(0, root.handleX - Metrics.sliderHandle / 2 - Metrics.progressGap)
            height: parent.height
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeColor: Theme.m3primary
                strokeWidth: Metrics.sliderTrack
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap

                PathPolyline {
                    path: {
                        const points = [];
                        const w = Math.max(0, root.handleX - Metrics.sliderHandle / 2 - Metrics.progressGap);
                        const mid = track.height / 2;
                        for (let x = 0; x <= w; x += 2)
                            points.push(Qt.point(x, mid + Metrics.waveAmplitude * Math.sin((x / Metrics.waveLength + root._phase) * 2 * Math.PI)));
                        return points;
                    }
                }
            }
        }
    }

    Rectangle {
        id: handle

        objectName: "sliderHandle"
        x: root.handleX
        anchors.verticalCenter: parent.verticalCenter
        width: Metrics.sliderHandle
        height: Metrics.sliderHandle
        radius: width / 2
        color: Theme.m3primary

        // The handle's state layer: a halo of the handle colour (hover 8 %, focus/pressed 12 %).
        Rectangle {
            anchors.centerIn: parent
            width: Metrics.sliderTarget
            height: Metrics.sliderTarget
            radius: width / 2
            color: Theme.m3primary
            opacity: root.disabled ? 0 : area.pressed || root.activeFocus ? Metrics.statePressed : area.containsMouse ? Metrics.stateHover : 0
        }
    }

    FocusRing {
        target: handle
        visible: root.activeFocus
    }

    MouseArea {
        id: area

        anchors.fill: parent
        enabled: !root.disabled
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        preventStealing: true
        onPressed: mouse => {
            root._dragging = true;
            root._set(root.from + (root.to - root.from) * Math.max(0, Math.min(1, (mouse.x - Metrics.sliderHandle / 2) / Math.max(1, root._track))));
        }
        onPositionChanged: mouse => {
            if (pressed)
                root._set(root.from + (root.to - root.from) * Math.max(0, Math.min(1, (mouse.x - Metrics.sliderHandle / 2) / Math.max(1, root._track))));
        }
        onReleased: {
            root._dragging = false;
            if (!root.live)
                root.moved(root.value);
            root.released(root.value);
        }
    }

    NumberAnimation on _phase {
        from: 0
        to: -1
        loops: Animation.Infinite
        duration: Theme.duration("extraLarge") * 2
        running: root.wavy && root.waveMoving && root.visible && !Motion.reduced
    }
}
