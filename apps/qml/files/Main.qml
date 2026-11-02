// Wysun Files: adaptive navigation with the places (modal drawer / rail / drawer), the tabs, a top bar with history,
// the path and the view switch, one FolderView per tab, the floating selection bar and the status line. Python
// provides `files` (tabs and settings), `places` and `bridge` (theme); later parts add operations and the preview.
import QtQuick
import WysunM3
import "parts"

Window {
    id: window

    readonly property var tab: files.current
    readonly property var model: tab ? tab.model : null
    readonly property Item overlayHost: overlay
    readonly property var snackbarHost: snackbars
    readonly property Item currentView: views.itemAt(files.currentIndex)

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
        if (pathBar.editing) {
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

    function keyAction(action) {
        files.keyAction(action, model ? model.selectedPaths : []);
    }

    title: files.title
    width: 1180
    height: 780
    minimumWidth: Metrics.windowMedium * 0.6
    minimumHeight: Metrics.windowMedium * 0.7
    color: Theme.m3surface

    Item {
        id: root

        objectName: "filesRoot"
        anchors.fill: parent

        ThemeFeed {
            scheme: bridge.scheme
            tokens: bridge.tokens
            reducedMotion: bridge.reducedMotion
        }

        AdaptiveNavigation {
            id: nav

            objectName: "filesNav"
            anchors.fill: parent
            windowWidth: window.width
            destinations: places.destinations
            currentId: window.tab ? places.placeOf(window.tab.path) : ""
            onDestinationSelected: id => window.navigate(id)
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
                    onClicked: window.keyAction("new")
                }
            }
            fab: Component {
                Fab {
                    icon: "add"
                    onClicked: window.keyAction("new")
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
                            objectName: "moreButton"
                            anchors.verticalCenter: parent.verticalCenter
                            icon: "more_vert"
                            onClicked: {
                                const point = mapToItem(null, 0, height);
                                files.moreMenu(point.x, point.y);
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

                    Repeater {
                        id: views

                        model: files.tabs

                        FolderView {
                            required property var modelData
                            required property int index

                            objectName: "folderView"
                            anchors.fill: parent
                            visible: index === files.currentIndex
                            enabled: visible
                            focus: visible
                            tab: modelData
                            mode: files.viewMode
                            onOpened: paths => files.openFiles(paths)
                            onContextRequested: (paths, x, y) => files.contextMenu(paths, x, y)
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
                }
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
                sequence: "Ctrl+Q"
                onActivated: window.close()
            }
        }
    }
}
