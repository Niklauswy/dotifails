pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes
import Wysun.Config
import qs.components
import qs.services

// Annotations drawn over the frozen capture, inside `bounds`. Each mark is a
// plain object in `marks`; `draft` is the mark being drawn. Everything here is
// part of what gets exported, so no editing chrome lives in this item.
Item {
    id: root

    required property Item source
    property rect bounds
    property bool drawing: true

    property string tool: "arrow"
    property color colour: Colours.palette.m3error
    property int size: 1
    property var marks: []
    property var undone: []
    property var draft: null
    property int counter: 1
    readonly property bool editingText: draft?.type === "text"

    readonly property real stroke: [2, 4, 8][size]

    function push(mark: var): void {
        marks = marks.concat([mark]);
        undone = [];
    }

    function undo(): void {
        if (editingText)
            return commitText();
        if (!marks.length)
            return;
        const last = marks[marks.length - 1];
        marks = marks.slice(0, -1);
        undone = undone.concat([last]);
        if (last.type === "counter")
            counter = Math.max(1, counter - 1);
    }

    function redo(): void {
        if (!undone.length)
            return;
        const next = undone[undone.length - 1];
        undone = undone.slice(0, -1);
        marks = marks.concat([next]);
        if (next.type === "counter")
            counter++;
    }

    function commitText(): void {
        if (draft?.type === "text" && textEditor.text.trim().length)
            push(Object.assign({}, draft, { text: textEditor.text }));
        draft = null;
        textEditor.text = "";
    }

    function clamp(p: point): point {
        return Qt.point(Math.max(bounds.x, Math.min(bounds.x + bounds.width, p.x)), Math.max(bounds.y, Math.min(bounds.y + bounds.height, p.y)));
    }

    function begin(p: point): void {
        if (editingText)
            commitText();
        const base = { type: tool, colour: colour, stroke: stroke, size: size };
        if (tool === "text") {
            draft = Object.assign(base, { x: p.x, y: p.y });
            Qt.callLater(() => textEditor.forceActiveFocus());
        } else if (tool === "counter") {
            push(Object.assign(base, { x: p.x, y: p.y, n: counter++ }));
        } else if (tool === "pen" || tool === "marker") {
            draft = Object.assign(base, { points: [p] });
        } else {
            draft = Object.assign(base, { from: p, to: p });
        }
    }

    function extend(p: point): void {
        if (!draft || draft.type === "text")
            return;
        if (draft.points)
            draft = Object.assign({}, draft, { points: draft.points.concat([p]) });
        else
            draft = Object.assign({}, draft, { to: p });
    }

    function end(): void {
        if (!draft || draft.type === "text")
            return;
        const small = draft.from && Math.hypot(draft.to.x - draft.from.x, draft.to.y - draft.from.y) < 3;
        if (!small && !(draft.points && draft.points.length < 2))
            push(draft);
        draft = null;
    }

    // Region of a two-point mark.
    function boxOf(mark: var): rect {
        return Qt.rect(Math.min(mark.from.x, mark.to.x), Math.min(mark.from.y, mark.to.y), Math.abs(mark.to.x - mark.from.x), Math.abs(mark.to.y - mark.from.y));
    }

    Item {
        id: canvas

        x: root.bounds.x
        y: root.bounds.y
        width: root.bounds.width
        height: root.bounds.height
        clip: true

        Repeater {
            model: root.marks

            Mark {}
        }

        Mark {
            modelData: root.draft && root.draft.type !== "text" ? root.draft : null
            visible: !!modelData
        }

        TextEdit {
            id: textEditor

            visible: root.editingText
            x: (root.draft?.x ?? 0) - root.bounds.x
            y: (root.draft?.y ?? 0) - root.bounds.y
            width: Math.max(implicitWidth, Tokens.spacing.extraLarge)
            color: root.draft?.colour ?? root.colour
            font: Tokens.font.title.builders.large.weight(Font.Bold).scale([0.8, 1, 1.5][root.draft?.size ?? 1]).build()
            cursorDelegate: StyledRect {
                width: 2
                color: textEditor.color
            }

            Keys.onPressed: event => {
                if (event.key === Qt.Key_Escape || ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !(event.modifiers & Qt.ShiftModifier))) {
                    root.commitText();
                    event.accepted = true;
                }
            }
        }
    }

    MouseArea {
        anchors.fill: canvas
        enabled: root.drawing
        cursorShape: root.tool === "text" ? Qt.IBeamCursor : Qt.CrossCursor
        preventStealing: true

        onPressed: event => root.begin(root.clamp(Qt.point(event.x + root.bounds.x, event.y + root.bounds.y)))
        onPositionChanged: event => root.extend(root.clamp(Qt.point(event.x + root.bounds.x, event.y + root.bounds.y)))
        onReleased: root.end()
    }

    // One mark, in coordinates relative to the canvas.
    component Mark: Item {
        id: mark

        required property var modelData
        readonly property real ox: root.bounds.x
        readonly property real oy: root.bounds.y
        readonly property string type: modelData?.type ?? ""
        readonly property rect box: modelData?.from ? root.boxOf(modelData) : Qt.rect(0, 0, 0, 0)

        anchors.fill: parent

        // Pixelate: the capture under the box, sampled down and scaled back up.
        ShaderEffectSource {
            visible: mark.type === "pixelate"
            x: mark.box.x - mark.ox
            y: mark.box.y - mark.oy
            width: mark.box.width
            height: mark.box.height
            sourceItem: visible ? root.source : null
            sourceRect: mark.box
            textureSize: Qt.size(Math.max(1, mark.box.width / 12), Math.max(1, mark.box.height / 12))
            smooth: false
            live: false
        }

        StyledRect {
            visible: mark.type === "rect"
            x: mark.box.x - mark.ox
            y: mark.box.y - mark.oy
            width: mark.box.width
            height: mark.box.height
            radius: Tokens.rounding.extraSmall
            color: "transparent"
            border.width: mark.modelData?.stroke ?? 0
            border.color: mark.modelData?.colour ?? "transparent"
        }

        Shape {
            anchors.fill: parent
            visible: ["pen", "marker", "line", "arrow", "ellipse"].includes(mark.type)
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeColor: mark.type === "marker" ? Qt.alpha(mark.modelData?.colour ?? "transparent", 0.4) : mark.modelData?.colour ?? "transparent"
                strokeWidth: mark.type === "marker" ? (mark.modelData?.stroke ?? 0) * 4 : mark.modelData?.stroke ?? 0
                fillColor: "transparent"
                capStyle: mark.type === "marker" ? ShapePath.FlatCap : ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin

                PathPolyline {
                    path: {
                        const m = mark.modelData;
                        if (!m)
                            return [];
                        if (m.points)
                            return m.points.map(p => Qt.point(p.x - mark.ox, p.y - mark.oy));
                        if (m.type === "line" || m.type === "arrow")
                            return [Qt.point(m.from.x - mark.ox, m.from.y - mark.oy), Qt.point(m.to.x - mark.ox, m.to.y - mark.oy)];
                        return [];
                    }
                }
            }

            // Arrow head.
            ShapePath {
                strokeColor: "transparent"
                fillColor: mark.type === "arrow" ? mark.modelData?.colour ?? "transparent" : "transparent"

                PathPolyline {
                    path: {
                        const m = mark.modelData;
                        if (mark.type !== "arrow" || !m)
                            return [];
                        const a = Math.atan2(m.to.y - m.from.y, m.to.x - m.from.x);
                        const len = m.stroke * 4 + 10, spread = 0.45;
                        const tip = Qt.point(m.to.x - mark.ox, m.to.y - mark.oy);
                        const left = Qt.point(tip.x - len * Math.cos(a - spread), tip.y - len * Math.sin(a - spread));
                        const right = Qt.point(tip.x - len * Math.cos(a + spread), tip.y - len * Math.sin(a + spread));
                        return [tip, left, right, tip];
                    }
                }
            }

            ShapePath {
                strokeColor: mark.type === "ellipse" ? mark.modelData?.colour ?? "transparent" : "transparent"
                strokeWidth: mark.modelData?.stroke ?? 0
                fillColor: "transparent"

                PathAngleArc {
                    centerX: mark.box.x - mark.ox + mark.box.width / 2
                    centerY: mark.box.y - mark.oy + mark.box.height / 2
                    radiusX: mark.type === "ellipse" ? mark.box.width / 2 : 0
                    radiusY: mark.type === "ellipse" ? mark.box.height / 2 : 0
                    sweepAngle: 360
                }
            }
        }

        StyledText {
            visible: mark.type === "text"
            x: (mark.modelData?.x ?? 0) - mark.ox
            y: (mark.modelData?.y ?? 0) - mark.oy
            text: mark.modelData?.text ?? ""
            color: mark.modelData?.colour ?? "transparent"
            font: Tokens.font.title.builders.large.weight(Font.Bold).scale([0.8, 1, 1.5][mark.modelData?.size ?? 1]).build()
        }

        StyledRect {
            readonly property real diameter: [22, 30, 42][mark.modelData?.size ?? 1]

            visible: mark.type === "counter"

            x: (mark.modelData?.x ?? 0) - mark.ox - diameter / 2
            y: (mark.modelData?.y ?? 0) - mark.oy - diameter / 2
            width: diameter
            height: diameter
            radius: Tokens.rounding.full
            color: mark.modelData?.colour ?? "transparent"
            border.width: 2
            border.color: Colours.palette.m3surface

            StyledText {
                anchors.centerIn: parent
                text: mark.modelData?.n ?? ""
                color: Colours.palette.m3surface
                font: Tokens.font.label.builders.large.weight(Font.Bold).scale(parent.diameter / 30).build()
            }
        }
    }
}
