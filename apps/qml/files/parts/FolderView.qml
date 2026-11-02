// What a tab shows: the folder header, the filters and the files as a grid or a list (F-20…F-30). The selection
// lives in the FolderModel; this view turns clicks, a rubber band and keys into it. Opening, menus and the preview
// are the window's: the view only asks (`opened`, `contextRequested`, `previewRequested`).
import QtQuick
import WysunM3

FocusScope {
    id: root

    property var tab                        // controller.Tab
    readonly property var model: tab ? tab.model : null
    property string mode: "grid"            // grid | list
    property bool chooser                   // the file chooser: no destructive keys
    property bool multiSelect: true         // false: one file at a time (a chooser without `multiple`)
    property bool entering
    readonly property Item view: mode === "list" ? listLoader.item : gridLoader.item
    readonly property alias filters: headerFilters
    readonly property bool filtering: model ? (model.filterText !== "" || model.group !== "all") : false
    readonly property bool wide: width >= FilesMetrics.listColumnsFrom

    signal opened(var paths)                // files to open (folders navigate here)
    signal contextRequested(var paths, real x, real y)
    signal previewRequested
    signal keyAction(string action)         // copy cut paste trash rename… (the window acts on them)

    function focusFiles() {
        if (view)
            view.forceActiveFocus(Qt.TabFocusReason);
    }

    function beginFilter(text) {
        headerFilters.begin(text);
    }

    // The delegate of a row, scrolled into view first (keyboard menus, tests).
    function itemFor(row) {
        if (!view || row < 0)
            return null;
        view.positionViewAtIndex(row, ListView.Contain);
        view.forceLayout();
        return view.itemAtIndex(row);
    }

    function selectedPaths() {
        return model ? model.selectedPaths : [];
    }

    // A press on a file: left = single / Ctrl toggle / Shift range; right selects what it hits if needed.
    function press(index, button, modifiers) {
        view.forceActiveFocus(Qt.MouseFocusReason);
        if (button === Qt.MiddleButton) {
            const row = model.get(index);
            if (row.isDir && !root.chooser)
                files.newTab(row.path);
            return;
        }
        if (!root.multiSelect)
            modifiers = Qt.NoModifier;
        if (button === Qt.RightButton) {
            if (!model.get(index).selected)
                model.select(index, "single");
            return;
        }
        if (modifiers & Qt.ShiftModifier)
            model.select(index, "range");
        else if (modifiers & Qt.ControlModifier)
            model.select(index, "toggle");
        else
            model.select(index, "single");
    }

    function activate(index) {
        const row = model.get(index);
        if (!row.path)
            return;
        if (row.isDir) {
            tab.navigate(row.path);
            return;
        }
        const chosen = model.selectedPaths;
        root.opened(chosen.indexOf(row.path) >= 0 ? chosen : [row.path]);
    }

    function openSelection() {
        const chosen = model.selectedPaths;
        if (chosen.length === 1 && model.get(model.rowOf(chosen[0])).isDir)
            tab.navigate(chosen[0]);
        else if (chosen.length > 0)
            root.opened(chosen);
    }

    function contextAt(index, x, y) {
        root.contextRequested(index >= 0 ? model.selectedPaths : [], x, y);
    }

    // The keyboard menu (Alt+K, Menu): anchored on the current file, else the view's centre.
    function contextAtCurrent() {
        const row = model.currentRow;
        const item = row >= 0 && view ? view.itemAtIndex(row) : null;
        if (row >= 0 && !model.get(row).selected)
            model.select(row, "single");
        const point = item ? item.mapToItem(null, item.width / 2, item.height) : root.mapToItem(null, root.width / 2, root.height / 3);
        root.contextRequested(row >= 0 ? model.selectedPaths : [], point.x, point.y);
    }

    function columns() {
        return view && mode === "grid" ? Math.max(1, Math.floor(view.width / FilesMetrics.tileWidth)) : 1;
    }

    // Arrow keys move the current file and select it (Shift extends, Ctrl only moves).
    function move(step, modifiers) {
        if (!root.multiSelect)
            modifiers = modifiers & ~Qt.ShiftModifier;
        const count = model.count;
        if (count === 0)
            return;
        const from = model.currentRow < 0 ? -1 : model.currentRow;
        const target = from < 0 ? 0 : Math.max(0, Math.min(count - 1, from + step));
        if (modifiers & Qt.ShiftModifier)
            model.select(target, "range");
        else if (modifiers & Qt.ControlModifier)
            model.currentRow = target;
        else
            model.select(target, "single");
        view.positionViewAtIndex(target, ListView.Contain);
    }

    function handleKey(event) {
        const mods = event.modifiers & (Qt.ShiftModifier | Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier);
        const cols = columns();
        const page = view ? Math.max(1, Math.floor(view.height / (mode === "grid" ? FilesMetrics.tileHeight : FilesMetrics.rowHeight))) * cols : 10;
        const plain = (mods & ~Qt.ShiftModifier & ~Qt.ControlModifier) === 0;
        switch (event.key) {
        case Qt.Key_Right:
            if (mode === "grid" && plain) {
                move(1, mods);
                return true;
            }
            return false;
        case Qt.Key_Left:
            if (mode === "grid" && plain) {
                move(-1, mods);
                return true;
            }
            if (mode === "list" && mods === Qt.NoModifier) {
                tab.up();
                return true;
            }
            return false;
        case Qt.Key_Down:
            if (!plain)
                return false;
            move(cols, mods);
            return true;
        case Qt.Key_Up:
            if (!plain)
                return false;
            move(-cols, mods);
            return true;
        case Qt.Key_PageDown:
            move(page, mods);
            return true;
        case Qt.Key_PageUp:
            move(-page, mods);
            return true;
        case Qt.Key_Home:
            move(-model.count, mods);
            return true;
        case Qt.Key_End:
            move(model.count, mods);
            return true;
        case Qt.Key_Return:
        case Qt.Key_Enter:
            if (mods === Qt.NoModifier) {
                openSelection();
                return true;
            }
            return false;
        case Qt.Key_Backspace:
            if (mods === Qt.NoModifier) {
                tab.up();
                return true;
            }
            return false;
        case Qt.Key_Space:
            if (mods === Qt.NoModifier) {
                root.previewRequested();
                return true;
            }
            return false;
        case Qt.Key_Menu:
            contextAtCurrent();
            return true;
        case Qt.Key_A:
            if (mods === Qt.ControlModifier) {
                if (root.multiSelect)
                    model.selectAll();
                return true;
            }
            break;
        case Qt.Key_Delete:
            if (!root.chooser && mods === Qt.NoModifier) {
                root.keyAction("trash");
                return true;
            }
            return false;
        case Qt.Key_F2:
            if (!root.chooser) {
                root.keyAction("rename");
                return true;
            }
            return false;
        case Qt.Key_C:
            if (mods === Qt.ControlModifier && !root.chooser) {
                root.keyAction("copy");
                return true;
            }
            break;
        case Qt.Key_X:
            if (mods === Qt.ControlModifier && !root.chooser) {
                root.keyAction("cut");
                return true;
            }
            break;
        case Qt.Key_V:
            if (mods === Qt.ControlModifier && !root.chooser) {
                root.keyAction("paste");
                return true;
            }
            break;
        }
        // Typing starts the filter (F-30).
        if ((mods === Qt.NoModifier || mods === Qt.ShiftModifier) && event.text.length === 1 && event.text.charCodeAt(0) > 32 && event.text.charCodeAt(0) !== 127) {
            beginFilter(event.text);
            return true;
        }
        return false;
    }

    function enter() {
        entering = true;
        settle.restart();
    }

    Timer {
        id: settle

        interval: 0
        onTriggered: root.entering = false
    }

    Connections {
        target: root.model

        function onLoaded(path) {
            if (!root.view)
                return;
            root.view.positionViewAtBeginning();
            if (root.model.currentRow >= 0)
                root.view.positionViewAtIndex(root.model.currentRow, ListView.Center);
            root.enter();
        }

        function onCurrentRowChanged() {
            if (root.view && root.model.currentRow >= 0) {
                root.view.currentIndex = root.model.currentRow;
                root.view.positionViewAtIndex(root.model.currentRow, ListView.Contain);
            }
        }
    }

    onModeChanged: {
        Qt.callLater(() => {
            if (view && model && model.currentRow >= 0)
                view.positionViewAtIndex(model.currentRow, ListView.Center);
            enter();
        });
    }

    // ------------------------------------------------------------------ header (scrolls with the files)
    Component {
        id: headerComponent

        Column {
            width: ListView.view ? ListView.view.width : GridView.view.width
            topPadding: Theme.spacing.medium ?? 0
            bottomPadding: Theme.spacing.medium ?? 0
            spacing: Theme.spacing.medium ?? 0

            FolderHero {
                width: parent.width
                title: root.tab ? root.tab.title : ""
                summary: root.model ? root.model.summary : ""
                dominant: root.model ? root.model.dominant : ""
                glyph: root.tab ? root.tab.glyph : ""
            }
            Item {
                id: filterSlot

                width: parent.width
                height: headerFilters.implicitHeight
                Component.onCompleted: headerFilters.parent = filterSlot
            }
            ListHeader {
                visible: root.mode === "list"
                width: parent.width
                model: root.model
                wide: root.wide
            }
        }
    }

    // One FilterRow for both views (its focus and text survive switching grid ⇄ list).
    FilterRow {
        id: headerFilters

        objectName: "filters"
        width: parent ? parent.width : 0
        model: root.model
        chooser: root.chooser
        onLeave: root.focusFiles()
    }

    // ------------------------------------------------------------------ empty, loading and error states
    Component {
        id: footerComponent

        Item {
            readonly property bool empty: root.model && root.model.count === 0
            readonly property bool loading: root.model && root.model.loading && waited.done

            width: ListView.view ? ListView.view.width : GridView.view.width
            height: empty && (loading || !root.model.loading) ? Math.max(Metrics.emptyEmblemSize * 3, (ListView.view ?? GridView.view).height * 0.6) : 0
            visible: height > 0

            Timer {
                id: waited

                property bool done
                interval: 250
                running: root.model && root.model.loading
                onRunningChanged: if (running) done = false
                onTriggered: done = true
            }

            EmptyState {
                objectName: "emptyState"
                anchors.centerIn: parent
                width: Math.min(parent.width, Metrics.dialogMaxWidth)
                readonly property string state: !root.model ? "" : root.model.error !== "" ? "error" : parent.loading ? "loading" : root.filtering ? "nomatch" : "empty"
                emblemShape: ({error: "burst", loading: "sunny", nomatch: "clover", empty: "cookie"})[state] ?? "cookie"
                icon: ({error: "folder_off", loading: "hourglass_top", nomatch: "filter_alt_off", empty: "folder_open"})[state] ?? "folder_open"
                title: state === "error" ? root.model.error : state === "loading" ? "Cargando carpeta…" : state === "nomatch" ? "Nada coincide con el filtro" : "Esta carpeta está vacía"
                message: state === "nomatch" ? "Prueba con otro nombre u otro tipo." : state === "empty" && !root.chooser ? "Crea una carpeta o un archivo, o copia algo aquí." : ""
                actionText: state === "nomatch" ? "Quitar filtro" : state === "error" && root.tab && root.tab.canBack ? "Volver" : state === "empty" && !root.chooser ? "Nueva carpeta" : ""
                onAction: {
                    if (state === "nomatch") {
                        root.model.setFilterText("");
                        root.model.setGroup("all");
                    } else if (state === "error") {
                        root.tab.back();
                    } else {
                        root.keyAction("newFolder");
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ the two views
    component Wheel: WheelHandler {
        // Wheel and touchpad scrolling for a non-interactive view, kept inside its bounds.
        property Flickable flick

        target: null
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: event => {
            const step = event.pixelDelta.y !== 0 ? event.pixelDelta.y : event.angleDelta.y / 120 * FilesMetrics.rowHeight * 2;
            const top = flick.originY, bottom = flick.originY + Math.max(0, flick.contentHeight - flick.height);
            flick.contentY = Math.max(top, Math.min(bottom, flick.contentY - step));
            event.accepted = true;
        }
    }

    component Band: Item {
        // The rubber band (F-29): drag on the background to select; Ctrl adds to the selection.
        id: band

        property var flick

        objectName: "band"
        property point origin
        property var before: []
        property bool dragged                 // survives the release, which still emits clicked
        readonly property bool active: area.pressed && (Math.abs(area.mouseX - origin.x) > 4 || Math.abs(area.mouseY - origin.y) > 4)

        // Covers the view (below the delegates); content coordinates are the view's plus contentY.
        anchors.fill: parent
        z: -1

        Rectangle {
            visible: band.active
            x: Math.min(band.origin.x, area.mouseX)
            y: Math.min(band.origin.y, area.mouseY)
            width: Math.abs(area.mouseX - band.origin.x)
            height: Math.abs(area.mouseY - band.origin.y)
            radius: Theme.rounding.extraSmall ?? 0
            color: Qt.alpha(Theme.m3primary, 0.12)
            border.width: 1
            border.color: Theme.m3primary
        }

        MouseArea {
            id: area

            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onPressed: mouse => {
                band.flick.forceActiveFocus(Qt.MouseFocusReason);
                band.origin = Qt.point(mouse.x, mouse.y);
                band.dragged = false;
                band.before = mouse.modifiers & Qt.ControlModifier ? root.model.selectedPaths : [];
            }
            onPositionChanged: mouse => {
                if (!band.active || !root.multiSelect)
                    return;
                band.dragged = true;
                const left = Math.min(band.origin.x, mouse.x), right = Math.max(band.origin.x, mouse.x);
                const top = Math.min(band.origin.y, mouse.y) + band.flick.contentY, bottom = Math.max(band.origin.y, mouse.y) + band.flick.contentY;
                const shift = band.flick.contentX;
                const hit = [];
                for (let i = 0; i < root.model.count; ++i) {
                    const item = band.flick.itemAtIndex(i);
                    if (!item)
                        continue;
                    if (item.x - shift < right && item.x - shift + item.width > left && item.y < bottom && item.y + item.height > top)
                        hit.push(root.model.pathAt(i));
                }
                root.model.selectPaths(band.before.concat(hit.filter(p => band.before.indexOf(p) < 0)));
            }
            onClicked: mouse => {
                if (band.dragged)
                    return;
                if (mouse.button === Qt.RightButton) {
                    root.model.clearSelection();
                    const point = mapToItem(null, mouse.x, mouse.y);
                    root.contextRequested([], point.x, point.y);
                } else if (!(mouse.modifiers & Qt.ControlModifier)) {
                    root.model.clearSelection();
                }
            }
        }
    }

    Loader {
        id: gridLoader

        anchors.fill: parent
        anchors.leftMargin: FilesMetrics.pagePadding
        anchors.rightMargin: FilesMetrics.pagePadding
        active: root.mode === "grid"
        focus: active
        sourceComponent: GridView {
            id: grid

            objectName: "fileGrid"
            focus: true
            clip: true
            model: root.model
            cellWidth: Math.floor(width / Math.max(1, Math.floor(width / FilesMetrics.tileWidth)))
            cellHeight: FilesMetrics.tileHeight
            boundsBehavior: Flickable.StopAtBounds
            // No mouse flicking (it would take the press from the rubber band); the wheel is handled below.
            interactive: false
            keyNavigationEnabled: false
            currentIndex: root.model ? root.model.currentRow : -1
            highlightFollowsCurrentItem: false
            cacheBuffer: FilesMetrics.tileHeight * 2
            reuseItems: true
            header: headerComponent
            footer: footerComponent
            Keys.onPressed: event => event.accepted = root.handleKey(event)

            delegate: Item {
                id: cell

                required property int index
                required property var model

                width: grid.cellWidth
                height: grid.cellHeight

                FileTile {
                    anchors.horizontalCenter: parent.horizontalCenter
                    index: cell.index
                    model: cell.model
                    view: root
                    current: cell.index === grid.currentIndex
                }
            }

            Band {
                flick: grid
            }
            Wheel {
                flick: grid
            }

        }
    }

    Loader {
        id: listLoader

        anchors.fill: parent
        anchors.leftMargin: FilesMetrics.pagePadding
        anchors.rightMargin: FilesMetrics.pagePadding
        active: root.mode === "list"
        focus: active
        sourceComponent: ListView {
            id: list

            objectName: "fileList"
            focus: true
            clip: true
            model: root.model
            boundsBehavior: Flickable.StopAtBounds
            // No mouse flicking (it would take the press from the rubber band); the wheel is handled below.
            interactive: false
            keyNavigationEnabled: false
            currentIndex: root.model ? root.model.currentRow : -1
            highlightFollowsCurrentItem: false
            cacheBuffer: FilesMetrics.rowHeight * 10
            reuseItems: true
            header: headerComponent
            footer: footerComponent
            Keys.onPressed: event => event.accepted = root.handleKey(event)

            delegate: FileRow {
                width: ListView.view.width
                view: root
                wide: root.wide
                current: index === ListView.view.currentIndex
            }

            Band {
                flick: list
            }
            Wheel {
                flick: list
            }

        }
    }

    ScrollBar {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        flickable: root.view
    }
}
