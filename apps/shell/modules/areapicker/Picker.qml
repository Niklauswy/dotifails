pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Wysun.Config
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

    function choose(r: rect): void {
        session.selection = Qt.rect(Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height));
        session.phase = session.mode === "annotate" ? "edit" : "actions";
        forceActiveFocus();
    }

    function deliver(save: bool): void {
        if (annotations.editingText)
            annotations.commitText();
        session.deliver(frame, save);
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
    cursorShape: phase === "actions" ? (grab ? Qt.ClosedHandCursor : Qt.ArrowCursor) : Qt.CrossCursor
    focus: active
    opacity: ready ? 1 : 0

    onActiveChanged: if (active)
        forceActiveFocus()

    onPositionChanged: event => {
        pointer = Qt.point(event.x, event.y);
        if (selecting && !session.busy && session.screenName !== screen.name && !dragging) {
            session.screenName = screen.name;
            strings.settle();
        }
        if (selecting) {
            if (pressed && !dragging && Math.hypot(event.x - pressAt.x, event.y - pressAt.y) > minSize)
                dragging = true;
            if (!dragging)
                hovered = windowAt(event.x, event.y);
        } else if (pressed && grab && phase === "actions") {
            adjust(event.x, event.y);
        }
    }

    onPressed: event => {
        pressAt = Qt.point(event.x, event.y);
        if (phase === "actions") {
            grab = cornerAt(event.x, event.y);
            grabStart = session.selection;
            if (!grab) {
                // Outside the region: draw a new one.
                session.phase = "select";
                hovered = Qt.rect(0, 0, 0, 0);
            }
        }
    }

    onReleased: event => {
        if (phase === "actions") {
            grab = "";
            return;
        }
        if (!selecting)
            return;
        if (dragging) {
            dragging = false;
            if (region.width >= minSize && region.height >= minSize)
                choose(region);
        } else {
            // A click takes the window under the pointer, or the whole output.
            const w = windowAt(event.x, event.y);
            choose(w.width > 0 ? w : Qt.rect(0, 0, width, height));
        }
    }

    Keys.onPressed: event => {
        const ctrl = event.modifiers & Qt.ControlModifier;
        const shift = event.modifiers & Qt.ShiftModifier;
        const enter = event.key === Qt.Key_Return || event.key === Qt.Key_Enter;
        if (event.key === Qt.Key_Escape) {
            if (phase === "edit" && annotations.editingText)
                annotations.commitText();
            else
                session.finished();
        } else if (selecting && enter) {
            choose(Qt.rect(0, 0, width, height));
        } else if (phase === "actions" && (enter || (ctrl && event.key === Qt.Key_C))) {
            root.deliver(root.session.autoSave);
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
                root.deliver(true);
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
        visible: root.active && root.ready
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
        saves: root.session.autoSave
        onCopy: root.deliver(root.session.autoSave)
        onAnnotate: root.session.phase = "edit"
        onReadText: {
            root.session.recognise(frame);
            Qt.callLater(() => ocrPanel.focusText());
        }
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
        saves: root.session.autoSave
        onCopy: root.deliver(root.session.autoSave)
        onSave: root.deliver(true)
        onCancel: root.session.finished()
    }

    component Band: Rectangle {
        color: Colours.palette.m3scrim
    }
}
