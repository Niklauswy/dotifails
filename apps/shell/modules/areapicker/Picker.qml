pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services

// One output of a screenshot. The output is frozen at open; the selection lives
// on the output under the pointer, hanging from strings tied to its corners.
// Click picks the window under the pointer, drag draws a region, Enter takes the
// whole output. Afterwards the region can be moved or resized by its nodes.
MouseArea {
    id: root

    required property Session session
    required property ShellScreen screen

    readonly property bool active: session.screenName === screen.name
    readonly property bool ready: shot.hasContent
    readonly property string phase: session.phase
    readonly property bool selecting: phase === "select"
    readonly property int minSize: Tokens.sizes.screenshot.minSelection

    // Pointer, drag and the region under edit, in output coordinates.
    property point pointer: Qt.point(width / 2, height / 2)
    property point pressAt
    property bool dragging
    property string grab // "", "move", "tl", "tr", "bl", "br"
    // Holding Ctrl works as the left button: press, move, release.
    property bool keyDrag
    property rect grabStart
    property rect hovered: Qt.rect(0, 0, 0, 0)

    readonly property rect region: {
        if (selecting && dragging)
            return Qt.rect(Math.min(pressAt.x, pointer.x), Math.min(pressAt.y, pointer.y), Math.abs(pointer.x - pressAt.x), Math.abs(pointer.y - pressAt.y));
        if (!selecting)
            return session.selection;
        return Qt.rect(0, 0, 0, 0);
    }
    readonly property bool hasRegion: region.width > 0 && region.height > 0

    readonly property list<var> clients: {
        const mon = Hypr.monitorFor(screen);
        if (!mon)
            return [];
        const special = mon.lastIpcObject?.specialWorkspace;
        const wsId = special?.name ? special.id : mon.activeWorkspace?.id;
        if (wsId === undefined)
            return [];
        // Pinned, then fullscreen, then floating windows sit on top.
        return Hypr.toplevelsForWs(wsId).sort((a, b) => {
            const ac = a?.lastIpcObject, bc = b?.lastIpcObject;
            if (!ac || !bc)
                return !ac - !bc;
            return (bc.pinned - ac.pinned) || ((bc.fullscreen !== 0) - (ac.fullscreen !== 0)) || (bc.floating - ac.floating);
        });
    }

    function windowAt(x: real, y: real): rect {
        for (const client of clients) {
            const ipc = client?.lastIpcObject;
            if (!ipc?.at || !ipc?.size)
                continue;
            const cx = ipc.at[0] - screen.x, cy = ipc.at[1] - screen.y;
            if (x >= cx && y >= cy && x <= cx + ipc.size[0] && y <= cy + ipc.size[1])
                return Qt.rect(Math.max(0, cx), Math.max(0, cy), Math.min(width, cx + ipc.size[0]) - Math.max(0, cx), Math.min(height, cy + ipc.size[1]) - Math.max(0, cy));
        }
        return Qt.rect(0, 0, 0, 0);
    }

    // Recording picks one kind of target; the screenshot picker takes any.
    readonly property bool drawsAreas: !session.pick || session.pick === "area"

    function hoverTarget(x: real, y: real): rect {
        if (session.pick === "area")
            return Qt.rect(0, 0, 0, 0);
        if (session.pick === "screen")
            return Qt.rect(0, 0, width, height);
        return windowAt(x, y);
    }

    function chooseMode(what: string): void {
        session.pick = what;
        session.phase = "select";
        hovered = hoverTarget(pointer.x, pointer.y);
        forceActiveFocus();
    }

    function choose(r: rect): void {
        session.selection = Qt.rect(Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height));
        if (session.mode === "quick") {
            // Take it at once: copy, save and close.
            session.phase = "done";
            root.deliver(session.autoSave);
            return;
        }
        session.phase = session.mode === "record" ? "record" : "actions";
        forceActiveFocus();
    }

    function startRecording(): void {
        const r = session.selection;
        session.startRecording(screen, r.x <= 0 && r.y <= 0 && r.width >= width && r.height >= height);
    }

    function beginDrag(x: real, y: real): void {
        pressAt = Qt.point(x, y);
        if (phase === "actions" || phase === "record") {
            grab = cornerAt(x, y);
            const r = session.selection;
            grabStart = Qt.rect(r.x, r.y, r.width, r.height);
            if (!grab) {
                // Outside the region: draw a new one.
                session.phase = "select";
                hovered = Qt.rect(0, 0, 0, 0);
            }
        }
    }

    function moveDrag(x: real, y: real, held: bool): void {
        pointer = Qt.point(x, y);
        if ((selecting || phase === "mode") && !session.busy && session.screenName !== screen.name && !dragging) {
            session.screenName = screen.name;
            strings.settle();
        }
        if (selecting) {
            if (held && !dragging && drawsAreas && Math.hypot(x - pressAt.x, y - pressAt.y) > minSize)
                dragging = true;
            if (!dragging)
                hovered = hoverTarget(x, y);
        } else if (held && grab && (phase === "actions" || phase === "record")) {
            adjust(x, y);
        }
    }

    function endDrag(x: real, y: real): void {
        if (phase === "actions" || phase === "record") {
            grab = "";
            return;
        }
        if (!selecting)
            return;
        if (dragging) {
            // Copy the region before ending the drag: it is derived from `dragging`,
            // and a plain read would stay a live reference to the property.
            const drawn = Qt.rect(region.x, region.y, region.width, region.height);
            dragging = false;
            if (drawn.width >= minSize && drawn.height >= minSize)
                choose(drawn);
        } else {
            // A click takes the window under the pointer, or the whole output;
            // when recording, only what the chosen mode allows.
            const w = windowAt(x, y);
            if (session.pick === "screen" || (!session.pick && w.width <= 0))
                choose(Qt.rect(0, 0, width, height));
            else if (session.pick !== "area" && w.width > 0)
                choose(w);
        }
    }

    function deliver(save: bool): void {
        if (annotations.editingText)
            annotations.commitText();
        session.deliver(frame, save);
    }

    function saveAs(): void {
        if (annotations.editingText)
            annotations.commitText();
        session.saveAs(frame);
    }

    function cornerAt(x: real, y: real): string {
        const r = session.selection, hit = Tokens.sizes.screenshot.handleHitSize / 2;
        const corners = { tl: [r.x, r.y], tr: [r.x + r.width, r.y], bl: [r.x, r.y + r.height], br: [r.x + r.width, r.y + r.height] };
        for (const [name, [cx, cy]] of Object.entries(corners))
            if (Math.abs(x - cx) <= hit && Math.abs(y - cy) <= hit)
                return name;
        if (x > r.x && y > r.y && x < r.x + r.width && y < r.y + r.height)
            return "move";
        return "";
    }

    function adjust(x: real, y: real): void {
        const s = grabStart, dx = x - pressAt.x, dy = y - pressAt.y;
        let l = s.x, t = s.y, r = s.x + s.width, b = s.y + s.height;
        if (grab === "move") {
            l = Math.max(0, Math.min(width - s.width, s.x + dx));
            t = Math.max(0, Math.min(height - s.height, s.y + dy));
            r = l + s.width;
            b = t + s.height;
        } else {
            if (grab.includes("l"))
                l = Math.max(0, Math.min(r - minSize, s.x + dx));
            if (grab.includes("r"))
                r = Math.min(width, Math.max(l + minSize, s.x + s.width + dx));
            if (grab.includes("t"))
                t = Math.max(0, Math.min(b - minSize, s.y + dy));
            if (grab.includes("b"))
                b = Math.min(height, Math.max(t + minSize, s.y + s.height + dy));
        }
        session.selection = Qt.rect(l, t, r - l, b - t);
    }

    // Keeps a floating panel next to the region, inside the output.
    function place(item: Item): point {
        const r = region, gap = Tokens.sizes.screenshot.toolbarGap;
        let y = r.y + r.height + gap;
        if (y + item.height > height - gap)
            y = r.y - item.height - gap;
        if (y < gap)
            y = Math.min(height - item.height - gap, r.y + r.height - item.height - gap);
        const x = Math.max(gap, Math.min(width - item.width - gap, r.x + r.width / 2 - item.width / 2));
        return Qt.point(x, y);
    }

    anchors.fill: parent
    hoverEnabled: true
    cursorShape: phase === "mode" ? Qt.ArrowCursor : phase === "actions" || phase === "record" ? (grab ? Qt.ClosedHandCursor : Qt.ArrowCursor) : Qt.BlankCursor
    focus: active
    opacity: ready ? 1 : 0

    onActiveChanged: if (active)
        forceActiveFocus()

    onPositionChanged: event => moveDrag(event.x, event.y, pressed || keyDrag)
    onPressed: event => beginDrag(event.x, event.y)
    onReleased: event => endDrag(event.x, event.y)

    Keys.onPressed: event => {
        const ctrl = event.modifiers & Qt.ControlModifier;
        const shift = event.modifiers & Qt.ShiftModifier;
        const enter = event.key === Qt.Key_Return || event.key === Qt.Key_Enter;
        if (event.key === Qt.Key_Control && !event.isAutoRepeat && selecting && !pressed) {
            keyDrag = true;
            beginDrag(pointer.x, pointer.y);
        } else if (event.key === Qt.Key_Escape) {
            if (phase === "edit" && annotations.editingText)
                annotations.commitText();
            else if (session.mode === "record" && session.pick && (selecting || phase === "record")) {
                // One step back: from the target (or the options) to the choice of what to record.
                session.selection = Qt.rect(0, 0, 0, 0);
                session.pick = "";
                dragging = false;
                session.phase = "mode";
            } else
                session.finished();
        } else if (phase === "mode" && event.key >= Qt.Key_1 && event.key <= Qt.Key_3) {
            chooseMode(["screen", "window", "area"][event.key - Qt.Key_1]);
        } else if (selecting && enter && (!session.pick || session.pick === "screen")) {
            choose(Qt.rect(0, 0, width, height));
        } else if (phase === "record" && enter) {
            startRecording();
        } else if (phase === "record" && event.key === Qt.Key_M) {
            Recorder.setPref("record_mic", !Recorder.mic);
        } else if (phase === "record" && event.key === Qt.Key_S) {
            Recorder.setPref("record_system", !Recorder.system);
        } else if (phase === "record" && event.key === Qt.Key_V && Recorder.cameras.length > 0) {
            Recorder.setPref("record_camera", !Recorder.camera);
        } else if (phase === "record" && event.key === Qt.Key_C) {
            Recorder.setPref("record_cursor", !Recorder.cursor);
        } else if (phase === "actions" && (enter || (ctrl && event.key === Qt.Key_C))) {
            root.deliver(root.session.autoSave);
        } else if (phase === "actions" && event.key === Qt.Key_S) {
            root.saveAs();
        } else if (phase === "actions" && event.key === Qt.Key_A) {
            session.phase = "edit";
        } else if (phase === "actions" && event.key === Qt.Key_T) {
            session.recognise(frame);
            Qt.callLater(() => ocrPanel.focusText());
        } else if (phase === "edit" && !annotations.editingText) {
            if (ctrl && event.key === Qt.Key_Z)
                shift ? annotations.redo() : annotations.undo();
            else if (ctrl && event.key === Qt.Key_Y)
                annotations.redo();
            else if (ctrl && event.key === Qt.Key_S)
                root.saveAs();
            else if (enter || (ctrl && event.key === Qt.Key_C))
                root.deliver(root.session.autoSave);
            else if (!ctrl && event.key >= Qt.Key_1 && event.key <= Qt.Key_9)
                annotations.tool = toolbar.tools[event.key - Qt.Key_1].id;
            else
                return;
        } else {
            return;
        }
        event.accepted = true;
    }

    Keys.onReleased: event => {
        if (event.key === Qt.Key_Control && !event.isAutoRepeat && keyDrag) {
            keyDrag = false;
            endDrag(pointer.x, pointer.y);
            event.accepted = true;
        }
    }

    Behavior on opacity {
        Anim {
            type: Anim.StandardSmall
        }
    }

    // What gets exported: the frozen output and the marks on it.
    Item {
        id: frame

        anchors.fill: parent

        ScreencopyView {
            id: shot

            anchors.fill: parent
            captureSource: root.screen
            live: false
        }

        Annotations {
            id: annotations

            anchors.fill: parent
            source: shot
            bounds: root.session.selection
            visible: root.active && root.phase === "edit"
            drawing: visible
        }
    }

    // Dim everything but the region (or the window under the pointer), as four
    // bands around the hole: no offscreen layer per output.
    Item {
        id: dim

        readonly property rect hole: root.active && root.hasRegion ? strings.shown : root.active && root.selecting ? root.hovered : Qt.rect(0, 0, 0, 0)
        readonly property bool open: hole.width > 0 && hole.height > 0
        readonly property real holeTop: open ? Math.max(0, hole.y) : height
        readonly property real holeBottom: open ? Math.min(height, hole.y + hole.height) : height
        readonly property real holeLeft: open ? Math.max(0, hole.x) : 0
        readonly property real holeRight: open ? Math.min(width, hole.x + hole.width) : width

        anchors.fill: parent
        opacity: Tokens.sizes.screenshot.dimOpacity * (root.active ? 1 : 1.4)

        Band {
            width: dim.width
            height: dim.holeTop
        }

        Band {
            y: dim.holeBottom
            width: dim.width
            height: dim.height - dim.holeBottom
        }

        Band {
            y: dim.holeTop
            width: dim.holeLeft
            height: dim.holeBottom - dim.holeTop
        }

        Band {
            x: dim.holeRight
            y: dim.holeTop
            width: dim.width - dim.holeRight
            height: dim.holeBottom - dim.holeTop
        }
    }

    // Window under the pointer while choosing.
    StyledRect {
        visible: root.active && root.selecting && !root.dragging && root.hovered.width > 0
        x: root.hovered.x
        y: root.hovered.y
        width: root.hovered.width
        height: root.hovered.height
        radius: Tokens.rounding.small
        color: "transparent"
        border.width: Tokens.sizes.screenshot.outlineWidth
        border.color: Qt.alpha(Colours.palette.m3primary, 0.5)
    }

    Strings {
        id: strings

        anchors.fill: parent
        visible: root.active && root.ready && root.phase !== "mode"
        single: !root.hasRegion
        tl: root.hasRegion ? Qt.point(root.region.x, root.region.y) : root.pointer
        tr: root.hasRegion ? Qt.point(root.region.x + root.region.width, root.region.y) : root.pointer
        bl: root.hasRegion ? Qt.point(root.region.x, root.region.y + root.region.height) : root.pointer
        br: root.hasRegion ? Qt.point(root.region.x + root.region.width, root.region.y + root.region.height) : root.pointer
    }

    ActionBar {
        id: actionBar

        readonly property point at: root.place(this)

        x: at.x
        y: at.y
        visible: root.active && root.phase === "actions" && !root.grab
        onCopy: root.deliver(root.session.autoSave)
        onSaveAs: root.saveAs()
        onAnnotate: root.session.phase = "edit"
        onReadText: {
            root.session.recognise(frame);
            Qt.callLater(() => ocrPanel.focusText());
        }
        onCancel: root.session.finished()
    }

    ModeBar {
        id: modeBar

        x: Math.round((root.width - width) / 2)
        y: Math.round(root.height * 0.72)
        visible: root.active && root.phase === "mode"
        onChosen: what => root.chooseMode(what)
        onCancel: root.session.finished()
    }

    // What to do next, while choosing a target to record.
    StyledRect {
        visible: root.active && root.selecting && root.session.mode === "record" && !root.dragging
        x: Math.round((root.width - width) / 2)
        y: Tokens.sizes.screenshot.toolbarGap * 2
        implicitWidth: hint.implicitWidth + Tokens.padding.large * 2
        implicitHeight: hint.implicitHeight + Tokens.padding.small * 2
        radius: Tokens.rounding.full
        color: Colours.palette.m3surfaceContainer
        border.width: 1
        border.color: Qt.alpha(Colours.palette.m3outlineVariant, 0.6)

        StyledText {
            id: hint

            anchors.centerIn: parent
            text: root.session.pick === "screen" ? Tr.tr("Click the screen to record · Esc to go back") : root.session.pick === "window" ? Tr.tr("Click a window to record · Esc to go back") : Tr.tr("Drag to choose the area · Esc to go back")
            font: Tokens.font.label.builders.large.weight(Font.Medium).build()
        }
    }

    RecordBar {
        id: recordBar

        readonly property point at: root.place(this)

        x: at.x
        y: at.y
        visible: root.active && root.phase === "record" && !root.grab
        mic: Recorder.mic
        system: Recorder.system
        cursor: Recorder.cursor
        camera: Recorder.camera
        onStart: root.startRecording()
        onToggleMic: Recorder.setPref("record_mic", !Recorder.mic)
        onToggleSystem: Recorder.setPref("record_system", !Recorder.system)
        onToggleCursor: Recorder.setPref("record_cursor", !Recorder.cursor)
        onToggleCamera: Recorder.setPref("record_camera", !Recorder.camera)
        onCancel: root.session.finished()
    }

    OcrPanel {
        id: ocrPanel

        readonly property point at: root.place(this)

        x: at.x
        y: at.y
        visible: root.active && root.phase === "ocr"
        text: root.session.ocrText
        running: root.session.ocrRunning
        onCopy: text => root.session.copyText(text)
        onCancel: root.session.finished()
    }

    EditorToolbar {
        id: toolbar

        readonly property point at: root.place(this)

        x: at.x
        y: at.y
        visible: root.active && root.phase === "edit"
        annotations: annotations
        onCopy: root.deliver(root.session.autoSave)
        onSave: root.saveAs()
        onCancel: root.session.finished()
    }

    component Band: Rectangle {
        color: Colours.palette.m3scrim
    }
}
