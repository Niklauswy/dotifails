// Wysun Files: adaptive navigation with the places (modal drawer / rail / drawer), the tabs, a top bar with history,
// the path and the view switch, one FolderView per tab, the floating selection bar and the status line. Python
// provides `files` (tabs and settings), `places` and `bridge` (theme); later parts add operations and the preview.
import QtQuick
import QtMultimedia
import WysunM3
import "parts"

Window {
    id: window

    readonly property var tab: files.current
    readonly property var model: tab ? tab.model : null
    readonly property Item overlayHost: overlay
    readonly property var snackbarHost: snackbars
    readonly property Item currentView: views.itemAt(files.currentIndex)
    readonly property var dialogs: filesDialogs
    readonly property var menus: filesMenus
    property bool closeWhenIdle
    property string pendingProperties          // FileManager1.ShowItemProperties: shown once the folder is listed
    property bool expanded
    readonly property int mediaState: mediaPlayer.playbackState      // 0 stopped, 1 playing, 2 paused
    readonly property bool inspectorShown: files.inspector && width >= FilesMetrics.inspectorFrom && model !== null && model.selectionCount > 0 && !expanded
    readonly property bool previewing: inspectorShown || expanded
    // Code and Markdown take their colours from the theme's roles.
    readonly property var codeColours: ({
            keyword: Theme.m3primary,
            string: Theme.m3tertiary,
            number: Theme.m3secondary,
            comment: Theme.m3outline,
            function: Theme.m3primary,
            type: Theme.m3secondary,
            constant: Theme.m3tertiary,
            key: Theme.m3secondary,
            meta: Theme.m3outline,
            link: Theme.m3primary,
            code_bg: Theme.m3surfaceContainerHighest,
            code_fg: Theme.m3onSurface,
            muted: Theme.m3onSurfaceVariant,
            text: Theme.m3onSurface,
            mono: Theme.font.family?.mono ?? ""
        })
    onCodeColoursChanged: preview.setColors(codeColours)
    onPreviewingChanged: updatePreview()

    function updatePreview() {
        preview.setSelection(previewing && model ? model.selectedPaths : []);
    }

    // Space (F-53): the expanded view of the one selected file.
    function togglePreview() {
        if (expanded) {
            closePreview();
            return;
        }
        const chosen = model ? model.selectedPaths : [];
        if (chosen.length !== 1 || model.get(model.rowOf(chosen[0])).isDir) {
            snackbars.show({text: "Selecciona un archivo para verlo en grande"});
            return;
        }
        expanded = true;
        updatePreview();
        expandedView.forceActiveFocus();
    }

    function closePreview() {
        if (window.visibility === Window.FullScreen)
            window.showNormal();
        expanded = false;
        focusFiles();
    }

    // ← / → in the expanded view: the next file of the same kind in the folder's order.
    function stepPreview(delta) {
        const current = model.currentRow;
        if (current < 0)
            return;
        const kind = model.get(current).kind;
        for (let row = current + delta; row >= 0 && row < model.count; row += delta) {
            if (model.get(row).kind === kind) {
                model.select(row, "single");
                updatePreview();
                return;
            }
        }
    }

    function followLink(href) {
        const target = preview.resolveLink(href);
        if (target === "")
            return;
        if (target.indexOf("://") > 0 || target.startsWith("mailto:")) {
            Qt.openUrlExternally(target);
            return;
        }
        if (expanded)
            closePreview();
        navigate(target);
    }

    function focusFiles() {
        currentView?.focusFiles();
    }

    function navigate(path) {
        if (!tab.navigate(path)) {
            snackbars.show({text: "No se puede abrir: " + path});
            return false;
        }
        focusFiles();
        return true;
    }

    // Escape, from the innermost thing outwards (F-30): path field, filter field, selection, filter text.
    function cancel() {
        if (window.visibility === Window.FullScreen && expanded) {
            window.showNormal();
            return;
        } else if (expanded) {
            closePreview();
            return;
        } else if (pathBar.editing) {
            pathBar.finish();
        } else if (currentView && currentView.filters.focused) {
            focusFiles();
        } else if (model && model.selectionCount > 0) {
            model.clearSelection();
        } else if (model && (model.filterText !== "" || model.group !== "all")) {
            model.setFilterText("");
            model.setGroup("all");
        } else {
            return;
        }
        focusFiles();
    }

    function openPaths(paths) {
        const folders = paths.filter(p => model.get(model.rowOf(p)).isDir === true);
        if (paths.length === 1 && folders.length === 1) {
            tab.navigate(paths[0]);
            return;
        }
        files.openFiles(paths.filter(p => folders.indexOf(p) < 0));
    }

    // What a key, a menu entry or a button asks for; `paths` defaults to the selection.
    function keyAction(action, paths) {
        const chosen = paths && paths.length > 0 ? paths : (model ? model.selectedPaths : []);
        switch (action) {
        case "copy":
            fileOps.copy(chosen);
            break;
        case "cut":
            fileOps.cut(chosen);
            break;
        case "paste":
            fileOps.paste(tab.path);
            break;
        case "trash":
            dialogs.confirmTrash(chosen);
            break;
        case "rename":
            if (chosen.length === 1)
                dialogs.askName("rename", tab.path, chosen[0]);
            break;
        case "newFolder":
        case "newFile":
            dialogs.askName(action, tab.path, "");
            break;
        case "new":
            {
                const point = newAnchor.mapToItem(null, 0, newAnchor.height);
                menus.newMenu(point.x, point.y);
            }
            break;
        case "open":
            openPaths(chosen);
            break;
        case "preview":
            togglePreview();
            break;
        }
    }

    title: files.title
    width: 1180
    height: 780
    minimumWidth: Metrics.windowMedium * 0.6
    minimumHeight: Metrics.windowMedium * 0.7
    color: Theme.m3surface
    // Closing waits for a running copy or move (F-05).
    onClosing: close => {
        mediaPlayer.stop();
        if (fileOps.busy) {
            close.accepted = false;
            closeWhenIdle = true;
            snackbars.show({text: "La ventana se cerrará cuando termine la operación"});
        }
    }

    Item {
        id: root

        objectName: "filesRoot"
        anchors.fill: parent

        ThemeFeed {
            scheme: bridge.scheme
            tokens: bridge.tokens
            reducedMotion: bridge.reducedMotion
        }
        Component.onCompleted: preview.setColors(window.codeColours)

        AdaptiveNavigation {
            id: nav

            objectName: "filesNav"
            anchors.fill: parent
            windowWidth: window.width
            destinations: places.destinations
            currentId: window.tab ? places.placeOf(window.tab.path) : ""
            onDestinationSelected: id => window.navigate(id)
            // Where «Nuevo» opens its menu: the top of the content, next to the drawer's button.
            Item {
                id: newAnchor

                x: Theme.padding.small ?? 0
                y: Theme.spacing.small ?? 0
                width: 1
                height: Metrics.fabRegular
            }
            onTrailingAction: id => places.eject(id)
            onContextRequested: (id, x, y) => {
                if (places.isBookmark(id)) {
                    placeMenu.target = id;
                    placeMenu.popup(null, x, y);
                }
            }
            header: Component {
                Fab {
                    objectName: "newFab"
                    extended: true
                    size: "small"
                    icon: "add"
                    text: "Nuevo"
                    onClicked: {
                        const point = mapToItem(null, 0, height + (Theme.spacing.small ?? 0));
                        window.menus.newMenu(point.x, point.y);
                    }
                }
            }
            fab: Component {
                Fab {
                    objectName: "newRailFab"
                    icon: "add"
                    onClicked: {
                        const point = mapToItem(null, width, 0);
                        window.menus.newMenu(point.x, point.y);
                    }
                }
            }

            Item {
                id: page

                anchors.fill: parent

                TabStrip {
                    id: tabStrip

                    x: FilesMetrics.pagePadding
                    y: visible ? Theme.spacing.small ?? 0 : 0
                    width: parent.width - 2 * x
                    height: visible ? implicitHeight : 0
                    visible: files.tabs.length > 1
                    tabs: files.tabs
                    currentIndex: files.currentIndex
                    onSelected: index => {
                        files.currentIndex = index;
                        window.focusFiles();
                    }
                    onClosed: index => files.closeTab(index)
                    onAdded: files.newTab("")
                }

                Item {
                    id: bar

                    objectName: "topBar"
                    anchors.top: tabStrip.bottom
                    width: parent.width
                    height: Metrics.topAppBarSmall

                    Row {
                        id: lead

                        x: Theme.padding.small ?? 0
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Theme.spacing.extraSmall ?? 0

                        IconButton {
                            visible: nav.menuButtonVisible
                            icon: "menu"
                            onClicked: nav.openModal()
                        }
                        IconButton {
                            objectName: "backButton"
                            icon: "arrow_back"
                            disabled: !window.tab || !window.tab.canBack
                            onClicked: window.tab.back()

                            Tooltip {
                                text: "Atrás · Alt+←"
                            }
                        }
                        IconButton {
                            objectName: "forwardButton"
                            visible: window.width >= Metrics.windowMedium
                            icon: "arrow_forward"
                            disabled: !window.tab || !window.tab.canForward
                            onClicked: window.tab.forward()

                            Tooltip {
                                text: "Adelante · Alt+→"
                            }
                        }
                        IconButton {
                            objectName: "upButton"
                            visible: window.width >= Metrics.windowMedium
                            icon: "arrow_upward"
                            disabled: !window.tab || !window.tab.canUp
                            onClicked: window.tab.up()

                            Tooltip {
                                text: "Carpeta superior · Alt+↑"
                            }
                        }
                    }

                    PathBar {
                        id: pathBar

                        objectName: "pathBar"
                        anchors.left: lead.right
                        anchors.leftMargin: Theme.spacing.small ?? 0
                        anchors.right: trail.left
                        anchors.rightMargin: Theme.spacing.small ?? 0
                        anchors.verticalCenter: parent.verticalCenter
                        tab: window.tab
                        onNavigateRequested: path => {
                            if (window.navigate(path))
                                pathBar.finish();
                        }
                        onCopyRequested: path => {
                            files.copyText(path);
                            snackbars.show({text: "Ruta copiada"});
                        }
                        onEditFinished: window.focusFiles()
                    }

                    Row {
                        id: trail

                        anchors.right: parent.right
                        anchors.rightMargin: Theme.padding.small ?? 0
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Theme.spacing.small ?? 0

                        SegmentedButtons {
                            objectName: "viewSwitch"
                            visible: window.width >= Metrics.windowMedium
                            anchors.verticalCenter: parent.verticalCenter
                            model: [{value: "grid", icon: "grid_view"}, {value: "list", icon: "view_list"}]
                            current: files.viewMode
                            onActivated: value => files.setViewMode(value)
                        }
                        IconButton {
                            objectName: "inspectorButton"
                            visible: window.width >= FilesMetrics.inspectorFrom
                            anchors.verticalCenter: parent.verticalCenter
                            icon: "right_panel_open"
                            checkable: true
                            checked: files.inspector
                            onClicked: files.setInspector(!files.inspector)

                            Tooltip {
                                text: "Vista previa · Ctrl+I"
                            }
                        }
                        IconButton {
                            objectName: "moreButton"
                            anchors.verticalCenter: parent.verticalCenter
                            icon: "more_vert"
                            onClicked: {
                                const point = mapToItem(null, 0, height);
                                window.menus.more(point.x, point.y);
                            }

                            Tooltip {
                                text: "Más acciones"
                            }
                        }
                    }
                }

                Item {
                    id: body

                    objectName: "filesBody"
                    anchors.top: bar.bottom
                    anchors.bottom: status.top
                    width: parent.width

                    Inspector {
                        id: inspector

                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: Theme.spacing.small ?? 0
                        width: FilesMetrics.inspectorWidth
                        x: window.inspectorShown ? parent.width - width - FilesMetrics.pagePadding : parent.width + FilesMetrics.pagePadding
                        visible: x < parent.width
                        player: mediaPlayer
                        onExpandRequested: window.togglePreview()
                        onLinkActivated: target => window.followLink(target)

                        Behavior on x {
                            Anim {
                                kind: "defaultSpatial"
                            }
                        }
                    }

                    Repeater {
                        id: views

                        model: files.tabs

                        FolderView {
                            required property var modelData
                            required property int index

                            objectName: "folderView"
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: parent.width - (window.inspectorShown ? FilesMetrics.inspectorWidth + FilesMetrics.pagePadding : 0)

                            Behavior on width {
                                Anim {
                                    kind: "defaultSpatial"
                                }
                            }
                            visible: index === files.currentIndex
                            enabled: visible
                            focus: visible
                            tab: modelData
                            mode: files.viewMode
                            onOpened: paths => window.openPaths(paths)
                            onContextRequested: (paths, x, y) => window.menus.context(paths, x, y)
                            onKeyAction: action => window.keyAction(action)
                            onPreviewRequested: window.keyAction("preview")
                        }
                    }

                }

                SelectionBar {
                    objectName: "selectionBar"
                    // Over the top bar, as in the mock-up (the folder's header stays readable).
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: bar.y + (bar.height - height) / 2
                    height: bar.height - (Theme.spacing.small ?? 0)
                    width: Math.min(parent.width - 2 * FilesMetrics.pagePadding, Metrics.dialogMaxWidth + Metrics.topAppBarSmall * 2)
                    count: window.model ? window.model.selectionCount : 0
                    onAction: id => id === "clear" ? window.model.clearSelection() : window.keyAction(id)
                    onMoreRequested: (x, y) => files.contextMenu(window.model.selectedPaths, x, y)
                }

                StatusLine {
                    id: status

                    anchors.bottom: parent.bottom
                    width: parent.width
                    model: window.model
                    free: window.tab ? window.tab.freeText : ""
                    operation: fileOps.busyText
                    progress: fileOps.progress
                }
            }
        }

        ExpandedPreview {
            id: expandedView

            anchors.fill: parent
            open: window.expanded
            player: mediaPlayer
            onCloseRequested: window.closePreview()
            onStepRequested: delta => window.stepPreview(delta)
            onFullScreenRequested: window.visibility === Window.FullScreen ? window.showNormal() : window.showFullScreen()
            onLinkActivated: target => window.followLink(target)
        }

        // One player for the inspector and the expanded view; a new file stops the previous one (F-51).
        MediaPlayer {
            id: mediaPlayer

            objectName: "mediaPlayer"
            source: window.previewing && (preview.kind === "video" || preview.kind === "audio") ? preview.mediaUrl : ""
            videoOutput: window.expanded ? expandedView.pane.videoOutput : inspector.pane.videoOutput
            audioOutput: AudioOutput {}
        }

        Connections {
            target: window.model

            function onLoaded(path) {
                if (window.pendingProperties !== "") {
                    window.dialogs.properties(window.pendingProperties);
                    window.pendingProperties = "";
                }
            }
            function onSelectionChanged() {
                if (window.previewing)
                    window.updatePreview();
            }
        }

        Connections {
            target: files

            function onCurrentChanged() {
                window.updatePreview();
            }
        }

        SnackbarHost {
            id: snackbars

            objectName: "snackbars"
            anchors.fill: parent
        }

        OverlayLayer {
            id: overlay
        }

        Connections {
            target: files

            function onMessage(text) {
                snackbars.show({text: text});
            }
        }

        Connections {
            target: fileOps

            function onMessage(text) {
                snackbars.show({text: text});
            }
            function onFailed(title, text) {
                snackbars.show({text: text, longer: true, closable: true});
            }
            function onTrashed(count) {
                snackbars.show({text: count === 1 ? "1 elemento en la papelera" : count + " elementos en la papelera", action: "Deshacer", longer: true});
            }
            function onFinished() {
                if (window.closeWhenIdle)
                    window.close();
            }
        }

        Connections {
            target: snackbars

            function onActionTriggered(action) {
                if (action === "Deshacer")
                    fileOps.undoTrash();
            }
        }

        FilesMenus {
            id: filesMenus

            app: window
            host: overlay
        }

        ShortcutSheet {
            id: shortcutSheet

            host: overlay
        }

        FilesDialogs {
            id: filesDialogs

            app: window
            host: overlay
        }

        Connections {
            target: places

            function onMessage(text) {
                snackbars.show({text: text});
            }
        }

        Menu {
            id: placeMenu

            property string target

            objectName: "placeMenu"
            host: overlay
            model: [{id: "open", text: "Abrir", icon: "folder_open"}, {id: "tab", text: "Abrir en nueva pestaña", icon: "tab"}, {divider: true}, {id: "remove", text: "Quitar de marcadores", icon: "bookmark_remove"}]
            onTriggered: id => {
                if (id === "open")
                    window.navigate(target);
                else if (id === "tab")
                    files.newTab(target);
                else if (id === "remove")
                    places.toggleBookmark(target);
            }
        }

        // Window-wide shortcuts (F-13, F-14, F-20, F-24, F-25, F-30); file actions live in FolderView.
        Item {
            Shortcut {
                sequence: "Escape"
                onActivated: window.cancel()
            }
            Shortcut {
                sequence: "Ctrl+1"
                onActivated: files.setViewMode("grid")
            }
            Shortcut {
                sequence: "Ctrl+2"
                onActivated: files.setViewMode("list")
            }
            Shortcut {
                sequence: "Ctrl+L"
                onActivated: pathBar.begin()
            }
            Shortcut {
                sequence: "Ctrl+F"
                onActivated: window.currentView?.beginFilter("")
            }
            Shortcut {
                sequence: "Ctrl+H"
                onActivated: files.setShowHidden(!files.showHidden)
            }
            Shortcut {
                sequence: "Ctrl+T"
                onActivated: files.newTab("")
            }
            Shortcut {
                sequence: "Ctrl+W"
                onActivated: files.closeTab(files.currentIndex)
            }
            Shortcut {
                sequences: ["Ctrl+Tab", "Ctrl+PgDown"]
                onActivated: files.cycleTab(1)
            }
            Shortcut {
                sequences: ["Ctrl+Shift+Tab", "Ctrl+PgUp", "Ctrl+Backtab"]
                onActivated: files.cycleTab(-1)
            }
            Shortcut {
                sequence: "Alt+Left"
                onActivated: window.tab.back()
            }
            Shortcut {
                sequence: "Alt+Right"
                onActivated: window.tab.forward()
            }
            Shortcut {
                sequence: "Alt+Up"
                onActivated: window.tab.up()
            }
            Shortcut {
                sequence: "Alt+Home"
                onActivated: window.navigate(files.homePath)
            }
            Shortcut {
                sequence: "Alt+K"
                onActivated: window.currentView?.contextAtCurrent()
            }
            Shortcut {
                sequence: "Ctrl+Shift+C"
                onActivated: {
                    files.copyText(window.tab.path);
                    snackbars.show({text: "Ruta copiada"});
                }
            }
            Shortcut {
                sequence: "Ctrl+Shift+N"
                onActivated: window.keyAction("newFolder")
            }
            Shortcut {
                sequence: "F1"
                onActivated: shortcutSheet.open()
            }
            Shortcut {
                sequence: "Ctrl+I"
                onActivated: files.setInspector(!files.inspector)
            }
            Shortcut {
                sequence: "Ctrl+Q"
                onActivated: window.close()
            }
        }
    }
}
