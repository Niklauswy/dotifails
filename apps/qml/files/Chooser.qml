// Wysun Files as a file chooser (files-chooser.html, F-62…F-67): the same navigation, path and folder view, without
// tabs, menus or destructive actions; at the bottom the file name (save), the portal's filters and choices, and
// Cancelar / the accept button. Enter enters a folder or accepts; Escape cancels. Python provides `chooser`.
import QtQuick
import WysunM3
import "parts"

Window {
    id: window

    readonly property var tab: files.current
    readonly property var model: tab ? tab.model : null
    readonly property var snackbarHost: snackbars
    readonly property bool saving: chooser.mode === "save"
    readonly property bool multipleAllowed: chooser.multiple      // FolderView's own `chooser` hides the bridge inside it

    function focusFiles() {
        folderView.focusFiles();
    }

    function navigate(path) {
        if (!tab.navigate(path)) {
            snackbars.show({text: "No se puede abrir: " + path});
            return false;
        }
        focusFiles();
        return true;
    }

    function accept() {
        chooser.accept(tab.path, model.selectedPaths, saveName.text);
    }

    function cancel() {
        if (pathBar.editing)
            pathBar.finish();
        else if (folderView.filters.focused)
            focusFiles();
        else
            chooser.cancel();
    }

    title: chooser.title
    width: 1100
    height: 740
    minimumWidth: Metrics.windowMedium * 0.6
    minimumHeight: Metrics.windowMedium * 0.7
    color: Theme.m3surface
    onClosing: chooser.cancel()

    Item {
        id: root

        objectName: "chooserRoot"
        anchors.fill: parent

        ThemeFeed {
            scheme: bridge.scheme
            tokens: bridge.tokens
            reducedMotion: bridge.reducedMotion
        }

        AdaptiveNavigation {
            id: nav

            objectName: "chooserNav"
            anchors.fill: parent
            windowWidth: window.width
            destinations: places.destinations
            currentId: window.tab ? places.placeOf(window.tab.path) : ""
            onDestinationSelected: id => window.navigate(id)

            Item {
                anchors.fill: parent

                Item {
                    id: bar

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
                            icon: "arrow_back"
                            disabled: !window.tab.canBack
                            onClicked: window.tab.back()
                        }
                        IconButton {
                            visible: window.width >= Metrics.windowMedium
                            icon: "arrow_forward"
                            disabled: !window.tab.canForward
                            onClicked: window.tab.forward()
                        }
                        IconButton {
                            visible: window.width >= Metrics.windowMedium
                            icon: "arrow_upward"
                            disabled: !window.tab.canUp
                            onClicked: window.tab.up()
                        }
                    }
                    PathBar {
                        id: pathBar

                        objectName: "pathBar"
                        anchors.left: lead.right
                        anchors.leftMargin: Theme.spacing.small ?? 0
                        anchors.right: viewSwitch.left
                        anchors.rightMargin: Theme.spacing.small ?? 0
                        anchors.verticalCenter: parent.verticalCenter
                        tab: window.tab
                        onNavigateRequested: path => {
                            if (window.navigate(path))
                                pathBar.finish();
                        }
                        onCopyRequested: path => files.copyText(path)
                        onEditFinished: window.focusFiles()
                    }
                    SegmentedButtons {
                        id: viewSwitch

                        visible: window.width >= Metrics.windowMedium
                        anchors.right: parent.right
                        anchors.rightMargin: Theme.padding.medium ?? 0
                        anchors.verticalCenter: parent.verticalCenter
                        model: [{value: "grid", icon: "grid_view"}, {value: "list", icon: "view_list"}]
                        current: files.viewMode
                        onActivated: value => files.setViewMode(value)
                    }
                }

                FolderView {
                    id: folderView

                    objectName: "folderView"
                    anchors.top: bar.bottom
                    anchors.bottom: footer.top
                    width: parent.width
                    focus: true
                    tab: window.tab
                    chooser: true
                    multiSelect: window.multipleAllowed
                    // Narrow choosers use the list, as the mock-up shows.
                    mode: window.width < Metrics.windowMedium ? "list" : files.viewMode
                    onOpened: paths => window.accept()
                }

                Connections {
                    target: window.model

                    // Saving: a file picked in the folder gives its name.
                    function onSelectionChanged() {
                        const chosen = window.model.selectedPaths;
                        if (window.saving && chosen.length === 1 && !window.model.get(window.model.rowOf(chosen[0])).isDir)
                            saveName.text = chosen[0].slice(chosen[0].lastIndexOf("/") + 1);
                    }
                }

                Rectangle {
                    id: footer

                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: column.implicitHeight + 2 * (Theme.padding.medium ?? 0)
                    color: Theme.m3surfaceContainer

                    Column {
                        id: column

                        x: FilesMetrics.pagePadding
                        y: Theme.padding.medium ?? 0
                        width: parent.width - 2 * x
                        spacing: Theme.spacing.small ?? 0

                        Label {
                            objectName: "chooserError"
                            visible: text !== ""
                            width: parent.width
                            role: "body.medium"
                            text: chooser.error
                            color: Theme.m3error
                            wrapMode: Text.Wrap
                        }
                        Item {
                            width: parent.width
                            height: Math.max(Metrics.textFieldHeight * (window.saving ? 1 : 0), actions.height, extras.height)

                            TextField {
                                id: saveName

                                objectName: "saveName"
                                visible: window.saving
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.min(parent.width - actions.width - extras.width - 2 * (Theme.spacing.medium ?? 0), Metrics.dialogMaxWidth)
                                label: "Nombre del archivo"
                                labelBackground: Theme.m3surfaceContainer
                                text: chooser.currentName
                                input.Keys.onReturnPressed: window.accept()
                                input.Keys.onEnterPressed: window.accept()
                                input.Keys.onEscapePressed: window.focusFiles()
                                // Saving starts in the name, with the part before the extension selected.
                                Component.onCompleted: {
                                    if (!window.saving)
                                        return;
                                    Qt.callLater(() => {
                                        input.forceActiveFocus();
                                        const dot = text.lastIndexOf(".");
                                        if (dot > 0)
                                            input.select(0, dot);
                                        else
                                            input.selectAll();
                                    });
                                }
                            }
                            Flow {
                                id: extras

                                anchors.left: window.saving ? saveName.right : parent.left
                                anchors.leftMargin: window.saving ? (Theme.spacing.medium ?? 0) : 0
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.min(implicitWidth, parent.width / 2)
                                spacing: Theme.spacing.small ?? 0

                                Button {
                                    id: filterButton

                                    objectName: "filterButton"
                                    visible: chooser.filters.length > 0
                                    type: "outlined"
                                    icon: "filter_list"
                                    text: chooser.filters[chooser.filterIndex] ?? ""
                                    onClicked: {
                                        const point = mapToItem(null, 0, 0);
                                        filterMenu.model = chooser.filters.map((name, i) => ({id: String(i), text: name, icon: i === chooser.filterIndex ? "check" : ""}));
                                        filterMenu.popup(null, point.x, point.y);
                                    }
                                }
                                Repeater {
                                    model: chooser.choices

                                    Item {
                                        id: choice

                                        required property var modelData

                                        width: modelData.toggle ? toggleChip.width : choiceButton.width
                                        height: Metrics.buttonHeight

                                        Chip {
                                            id: toggleChip

                                            visible: choice.modelData.toggle
                                            anchors.verticalCenter: parent.verticalCenter
                                            kind: "filter"
                                            text: choice.modelData.label
                                            selected: choice.modelData.value === "true"
                                            onClicked: chooser.setChoice(choice.modelData.id, choice.modelData.value === "true" ? "false" : "true")
                                        }
                                        Button {
                                            id: choiceButton

                                            visible: !choice.modelData.toggle
                                            type: "outlined"
                                            text: choice.modelData.label + ": " + choice.modelData.text
                                            onClicked: {
                                                const point = mapToItem(null, 0, 0);
                                                choiceMenu.choice = choice.modelData.id;
                                                choiceMenu.model = choice.modelData.options.map(o => ({id: o.value, text: o.text, icon: o.value === choice.modelData.value ? "check" : ""}));
                                                choiceMenu.popup(null, point.x, point.y);
                                            }
                                        }
                                    }
                                }
                            }
                            Row {
                                id: actions

                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: Theme.spacing.small ?? 0

                                Button {
                                    objectName: "cancelButton"
                                    type: "tonal"
                                    text: "Cancelar"
                                    onClicked: chooser.cancel()
                                }
                                Button {
                                    objectName: "acceptButton"
                                    type: "filled"
                                    icon: "check"
                                    text: chooser.acceptLabel
                                    onClicked: window.accept()
                                }
                            }
                        }
                    }
                }
            }
        }

        Menu {
            id: filterMenu

            host: overlay
            onTriggered: id => chooser.setFilter(Number(id))
        }

        Menu {
            id: choiceMenu

            property string choice

            host: overlay
            onTriggered: id => chooser.setChoice(choice, id)
        }

        Dialog {
            id: replaceDialog

            objectName: "replaceDialog"
            host: overlay
            icon: "warning"
            actions: [{id: "cancel", text: "Cancelar"}, {id: "replace", text: "Reemplazar", primary: true}]
            onAccepted: id => {
                if (id === "replace")
                    chooser.confirmReplace();
            }
        }

        Connections {
            target: chooser

            function onConfirmRequested(name, folder) {
                replaceDialog.title = "¿Reemplazar «" + name + "»?";
                replaceDialog.message = "Ya existe en «" + folder + "». La app que lo guarda lo sobrescribirá.";
                replaceDialog.open();
            }
        }

        SnackbarHost {
            id: snackbars

            anchors.fill: parent
        }

        OverlayLayer {
            id: overlay
        }

        Item {
            Shortcut {
                sequence: "Escape"
                onActivated: window.cancel()
            }
            Shortcut {
                sequence: "Ctrl+L"
                onActivated: pathBar.begin()
            }
            Shortcut {
                sequence: "Ctrl+F"
                onActivated: folderView.beginFilter("")
            }
            Shortcut {
                sequence: "Ctrl+H"
                onActivated: files.setShowHidden(!files.showHidden)
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
        }
    }
}
