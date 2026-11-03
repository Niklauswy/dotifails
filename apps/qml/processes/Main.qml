// Wysun Processes: an adaptive rail with four sections (Procesos, Rendimiento, Apps, Servicios), the
// confirmation dialog, the command palette, the shortcuts help and the snackbars. Python provides `procs` (the
// controller) and `bridge` (theme). Every section handles its own keys through handleKey(event).
import QtQuick
import WysunM3
import "parts"

Window {
    id: window

    property string page: "procs"
    readonly property Item overlayHost: overlay
    // Nothing animates while the window cannot be seen: on another workspace, minimised, or every output off.
    readonly property bool onScreen: visible && visibility !== Window.Minimized && !procs.suspended
    readonly property var order: ["procs", "perf", "apps", "services"]

    function loaderFor(id) {
        if (id === "procs")
            return procsLoader;
        if (id === "perf")
            return perfLoader;
        if (id === "apps")
            return appsLoader;
        if (id === "services")
            return servicesLoader;
        return null;
    }

    function pageItem(id) {
        const loader = loaderFor(id);
        return loader ? loader.item : null;
    }

    function go(id) {
        if (window.order.indexOf(id) < 0)
            return;
        page = id;
        procs.setPage(id);
        root.forceActiveFocus();
    }

    function anyOverlay() {
        return confirm.opened || palette.opened || help.opened;
    }

    width: 1280
    height: 820
    minimumWidth: 720
    minimumHeight: 480
    visible: false          // present() shows it once the app id (wysun-processes) is set
    title: "Wysun Processes"
    color: Theme.m3surface

    onVisibleChanged: procs.setWindowVisible(visible && visibility !== Window.Minimized)
    onVisibilityChanged: function (visibility) {
        procs.setWindowVisible(visible && visibility !== Window.Minimized);
    }
    Component.onCompleted: procs.setWindowVisible(visible && visibility !== Window.Minimized)

    Item {
        id: root

        objectName: "processesRoot"
        anchors.fill: parent
        focus: true

        ThemeFeed {
            scheme: bridge.scheme
            tokens: bridge.tokens
            reducedMotion: bridge.reducedMotion
        }

        Keys.onPressed: event => {
            const ctrl = event.modifiers & Qt.ControlModifier;
            if (ctrl && event.key === Qt.Key_K) {
                palette.open();
                event.accepted = true;
                return;
            }
            if (ctrl && event.key === Qt.Key_F) {
                window.go("procs");
                const procPage = window.pageItem("procs");
                if (procPage)
                    procPage.focusSearch();
                event.accepted = true;
                return;
            }
            if (ctrl || event.modifiers & Qt.AltModifier)
                return;
            if (event.text === "?") {
                help.open();
                event.accepted = true;
                return;
            }
            if (event.text >= "1" && event.text <= String(window.order.length)) {
                window.go(window.order[Number(event.text) - 1]);
                event.accepted = true;
                return;
            }
            if (event.text === "/") {
                window.go("procs");
                const procPage = window.pageItem("procs");
                if (procPage)
                    procPage.focusSearch();
                event.accepted = true;
                return;
            }
            const current = window.pageItem(window.page);
            if (current && current.handleKey(event))
                event.accepted = true;
        }

        AdaptiveNavigation {
            id: nav

            objectName: "processesNav"
            anchors.fill: parent
            windowWidth: window.width
            currentId: window.page
            destinations: [
                {id: "procs", icon: "list_alt", label: "Procesos"},
                {id: "perf", icon: "monitoring", label: "Rendimiento"},
                {id: "apps", icon: "apps", label: "Apps"},
                {id: "services", icon: "settings_suggest", label: "Servicios", badge: procs.failedCount > 0 ? procs.failedCount : undefined}
            ]
            fab: Component {
                Fab {
                    icon: "search"
                    onClicked: palette.open()
                }
            }
            onDestinationSelected: id => window.go(id)

            Item {
                id: pagesHost

                anchors.fill: parent

                // Only the current section exists: each page is a Loader and leaving it destroys its items. What the
                // user expects to keep (query, filters, selection, view mode) lives in the controller.
                Loader {
                    id: procsLoader

                    anchors.fill: parent
                    active: window.page === "procs"

                    sourceComponent: Component {
                        ProcessesPage {
                            objectName: "procsPage"
                            anchors.fill: parent
                            shown: window.page === "procs"
                            live: window.onScreen
                            overlayHost: overlay
                            onReturnFocus: root.forceActiveFocus()
                        }
                    }
                }

                Loader {
                    id: perfLoader

                    anchors.fill: parent
                    active: window.page === "perf"

                    sourceComponent: Component {
                        PerfPage {
                            objectName: "perfPage"
                            anchors.fill: parent
                            shown: window.page === "perf"
                            live: window.onScreen
                        }
                    }
                }

                Loader {
                    id: appsLoader

                    anchors.fill: parent
                    active: window.page === "apps"

                    sourceComponent: Component {
                        AppsPage {
                            objectName: "appsPage"
                            anchors.fill: parent
                            shown: window.page === "apps"
                            live: window.onScreen
                            onShowProcesses: app => {
                                window.go("procs");
                                procs.selectApp(app);
                            }
                        }
                    }
                }

                Loader {
                    id: servicesLoader

                    anchors.fill: parent
                    active: window.page === "services"

                    sourceComponent: Component {
                        ServicesPage {
                            objectName: "servicesPage"
                            anchors.fill: parent
                            shown: window.page === "services"
                            live: window.onScreen
                            onReturnFocus: root.forceActiveFocus()
                        }
                    }
                }
            }
        }

        ConfirmDialog {
            id: confirm

            objectName: "confirmDialog"
            host: overlay
            onClosedForFocus: root.forceActiveFocus()
        }

        CommandPalette {
            id: palette

            objectName: "commandPalette"
            anchors.fill: parent
            onGo: id => window.go(id)
            onClosed: root.forceActiveFocus()
        }

        ShortcutsHelp {
            id: help

            objectName: "shortcutsHelp"
            host: overlay
            onRejected: Qt.callLater(root.forceActiveFocus)
            onAccepted: Qt.callLater(root.forceActiveFocus)
        }

        SnackbarHost {
            id: snackbars

            objectName: "snackbars"
            anchors.fill: parent
            onActionTriggered: action => {
                if (action === "Deshacer")
                    procs.undo();
            }
        }

        OverlayLayer {
            id: overlay
        }

        Connections {
            target: procs

            function onMessage(text, undo) {
                snackbars.show(undo ? {text: text, action: "Deshacer"} : {text: text});
            }

            function onConfirmNeeded(action, label, count, nice) {
                confirm.ask(action, label, count, nice);
            }
        }
    }
}
