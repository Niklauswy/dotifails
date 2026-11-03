// Wysun Processes: an adaptive rail with five sections (Procesos, Rendimiento, Apps, Servicios, Inicio), the
// confirmation dialog, the command palette, the shortcuts help and the snackbars. Python provides `procs` (the
// controller) and `bridge` (theme). Every section handles its own keys through handleKey(event).
import QtQuick
import WysunM3
import "parts"

Window {
    id: window

    property string page: "procs"
    readonly property Item overlayHost: overlay
    readonly property var pages: ({ procs: procsPage, perf: perfPage, apps: appsPage, services: servicesPage, startup: startupPage })
    readonly property var order: ["procs", "perf", "apps", "services", "startup"]

    function go(id) {
        if (!pages[id])
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
    visible: true
    title: "Wysun Processes"
    color: Theme.m3surface

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
                procsPage.focusSearch();
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
            if (event.text >= "1" && event.text <= "5") {
                window.go(window.order[Number(event.text) - 1]);
                event.accepted = true;
                return;
            }
            if (event.text === "/") {
                window.go("procs");
                procsPage.focusSearch();
                event.accepted = true;
                return;
            }
            const current = window.pages[window.page];
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
                {id: "services", icon: "settings_suggest", label: "Servicios", badge: procs.failedCount > 0 ? procs.failedCount : undefined},
                {id: "startup", icon: "rocket_launch", label: "Inicio"}
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

                ProcessesPage {
                    id: procsPage

                    objectName: "procsPage"
                    anchors.fill: parent
                    shown: window.page === "procs"
                    overlayHost: overlay
                    onReturnFocus: root.forceActiveFocus()
                }

                PerfPage {
                    id: perfPage

                    anchors.fill: parent
                    shown: window.page === "perf"
                }

                AppsPage {
                    id: appsPage

                    anchors.fill: parent
                    shown: window.page === "apps"
                    onShowProcesses: app => {
                        window.go("procs");
                        procs.selectApp(app);
                    }
                }

                ServicesPage {
                    id: servicesPage

                    anchors.fill: parent
                    shown: window.page === "services"
                    onReturnFocus: root.forceActiveFocus()
                }

                StartupPage {
                    id: startupPage

                    anchors.fill: parent
                    shown: window.page === "startup"
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
