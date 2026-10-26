// Wysun Music: adaptive navigation (modal drawer / rail / drawer), a top bar with history and the library search,
// the routed pages, the player capsule and «Ahora suena». Python provides `music`, `covers`, `bridge` (theme) and,
// from later parts, `player`, `lyrics` and `addMusic`.
import QtQuick
import WysunM3
import "pages"
import "parts"

Window {
    id: window

    readonly property int historyLimit: 50
    property string route: ""
    property var history: []
    property var future: []
    readonly property string routeKind: route.split(":")[0]
    readonly property string routeRest: route.indexOf(":") >= 0 ? route.slice(route.indexOf(":") + 1) : ""
    readonly property bool detail: routeKind === "collection"
    property bool _refining
    // What pages reach through `app`.
    readonly property var menus: musicMenus
    readonly property var dialogs: playlistDialogs
    readonly property var snackbarHost: snackbars
    readonly property Item overlayHost: overlay

    function navigate(target, remember) {
        if (target === route) {
            if (routeKind === "search")
                search.forceFocus();
            return;
        }
        if (remember !== false && route !== "") {
            history = history.concat([route]).slice(-historyLimit);
            future = [];
        }
        const previousKind = routeKind;
        route = target;
        music.saveRoute(target);
        if (routeKind !== "search" && search.text !== "") {
            _refining = true;
            search.text = "";
            _refining = false;
        }
        showPage(previousKind);
    }

    function goBack() {
        if (history.length === 0)
            return;
        future = future.concat([route]);
        const target = history[history.length - 1];
        history = history.slice(0, -1);
        navigate(target, false);
    }

    function goForward() {
        if (future.length === 0)
            return;
        history = history.concat([route]);
        const target = future[future.length - 1];
        future = future.slice(0, -1);
        navigate(target, false);
    }

    // Destinations swap with fade through; a collection opens over them along the shared x axis.
    function showPage(previousKind) {
        const forward = previousKind !== "collection" || history.length === 0 || history[history.length - 1] !== route;
        if (detail) {
            details.show(collectionPage, {
                app: window,
                collectionId: routeRest
            }, forward);
            return;
        }
        details.clear();
        const component = ({
                home: homePage,
                search: searchPage,
                downloads: addMusicPage,
                library: libraryPage
            })[routeKind] ?? homePage;
        if (pages.currentItem && pages.currentItem.kind === routeKind) {
            pages.currentItem.route = route;          // same page, other tab or query
            return;
        }
        pages.show(component, {
            app: window,
            route: route
        }, true);
    }

    function drawerIdFor(target) {
        const kind = target.split(":")[0];
        return kind === "search" ? "search" : target;
    }

    function railIdFor(target) {
        const kind = target.split(":")[0];
        if (kind === "search")
            return "search";
        if (kind === "library")
            return target === "library:lists" ? "library:lists" : "library:albums";
        if (target === "collection:favorites" || target === "collection:recent")
            return "library:albums";
        return target;
    }

    // «Ahora suena» on a tab (now / lyrics / queue); the same key again closes it.
    property string panel: ""
    function togglePanel(tab) {
        if (tab === "" || (tab === panel && nowPlaying.open)) {
            panel = "";
            return;
        }
        panel = tab;
        nowPlaying.tab = tab === "queue" ? "queue" : "lyrics";
        nowPlaying.chosen = tab !== "now";
        nowPlaying.forceActiveFocus();
    }

    function focusContent() {
        (details.currentItem ?? pages.currentItem)?.forceActiveFocus(Qt.TabFocusReason);
    }

    title: "Wysun Music"
    width: 1280
    height: 820
    minimumWidth: Metrics.windowMedium * 0.6
    minimumHeight: Metrics.windowMedium * 0.8
    color: Theme.m3surface
    onClosing: close => {
        close.accepted = false;
        music.requestHide();
    }

    Component.onCompleted: navigate(music.routeExists(music.initialRoute) ? music.initialRoute : "home", false)

    Component {
        id: homePage

        HomePage {}
    }
    Component {
        id: libraryPage

        LibraryPage {}
    }
    Component {
        id: searchPage

        SearchPage {}
    }
    Component {
        id: addMusicPage

        AddMusicPage {}
    }
    Component {
        id: collectionPage

        CollectionPage {}
    }

    Item {
        id: root

        objectName: "musicRoot"
        anchors.fill: parent
        focus: true

        Keys.onEscapePressed: {
            if (window.panel !== "")
                window.panel = "";
            else
                music.requestHide();
        }
        // Space and M act on playback unless something focused (a text field, a button) took the key first.
        Keys.onPressed: event => {
            if (event.modifiers !== Qt.NoModifier && event.modifiers !== Qt.KeypadModifier)
                return;
            if (event.key === Qt.Key_Space) {
                player.toggle();
                event.accepted = true;
            } else if (event.key === Qt.Key_M) {
                player.toggleMute();
                event.accepted = true;
            }
        }

        Connections {
            target: player

            function onMessage(text) {
                snackbars.show(text);
            }
        }

        ThemeFeed {
            scheme: bridge.scheme
            tokens: bridge.tokens
            reducedMotion: bridge.reducedMotion
        }

        AdaptiveNavigation {
            id: nav

            objectName: "musicNav"
            anchors.fill: parent
            windowWidth: window.width
            destinations: music.destinations
            currentId: mode === "rail" ? window.railIdFor(window.route) : window.drawerIdFor(window.route)
            onDestinationSelected: id => window.navigate(id === "search" ? "search:" + search.text : id)
            onHeaderAction: id => {
                if (id === "new-playlist")
                    playlistDialogs.newPlaylist([]);
            }
            onContextRequested: (id, x, y) => musicMenus.collectionMenu(id.slice("collection:".length), root, x, y)

            Item {
                id: bar

                width: parent.width
                height: implicitHeight
                implicitHeight: Metrics.topAppBarSmall

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
                        objectName: "hideButton"
                        icon: "close"
                        onClicked: music.requestHide()

                        Tooltip {
                            text: "Ocultar · la música sigue sonando"
                        }
                    }
                    IconButton {
                        objectName: "backButton"
                        icon: "chevron_left"
                        disabled: window.history.length === 0
                        onClicked: window.goBack()

                        Tooltip {
                            text: "Atrás · Alt+←"
                        }
                    }
                    IconButton {
                        objectName: "forwardButton"
                        visible: window.width >= Metrics.windowMedium
                        icon: "chevron_right"
                        disabled: window.future.length === 0
                        onClicked: window.goForward()

                        Tooltip {
                            text: "Adelante · Alt+→"
                        }
                    }
                }

                SearchBar {
                    id: search

                    objectName: "searchBar"
                    x: lead.x + lead.width + (Theme.spacing.small ?? 0)
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(Metrics.textFieldMinWidth * 2.6, keys.x - x - (Theme.spacing.small ?? 0))
                    placeholder: "Buscar en tu biblioteca"
                    shortcut: ""
                    onTextChanged: {
                        if (window._refining)
                            return;
                        if (window.routeKind === "search") {
                            window.route = "search:" + text;      // typing refines the same history entry
                            music.saveRoute(window.route);
                            pages.currentItem && (pages.currentItem.route = window.route);
                        } else if (text !== "") {
                            window.navigate("search:" + text);
                        }
                    }
                    input.Keys.onDownPressed: window.focusContent()
                    onAccepted: window.focusContent()
                }

                IconButton {
                    id: keys

                    anchors.right: parent.right
                    anchors.rightMargin: Theme.padding.small ?? 0
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "keyboard"
                    onClicked: shortcutSheet.open()

                    Tooltip {
                        text: "Atajos de teclado · F1"
                    }
                }
    
            }

            Item {
                id: content

                objectName: "musicContent"
                y: bar.height
                width: parent.width
                height: parent.height - bar.height - capsule.height

                FadeThrough {
                    id: pages

                    objectName: "pages"
                    anchors.fill: parent
                    visible: !window.detail || details.running
                    clip: true
                }

                SharedAxis {
                    id: details

                    function clear() {
                        if (currentItem)
                            currentItem.destroy();
                        _current = null;
                    }

                    objectName: "details"
                    anchors.fill: parent
                    axis: "x"
                    clip: true
                }
            }

            PlayerCapsule {
                id: capsule

                app: window
                anchors.bottom: parent.bottom
                width: parent.width
                onPanelRequested: tab => window.togglePanel(tab)
            }
        }

        NowPlaying {
            id: nowPlaying

            anchors.fill: parent
            app: window
            open: window.panel !== ""
            onCloseRequested: {
                window.panel = "";
                root.forceActiveFocus();
            }
        }

        Binding {
            target: lyrics
            property: "active"
            value: nowPlaying.open
        }

        MusicMenus {
            id: musicMenus

            app: window
            host: overlay
        }

        PlaylistDialogs {
            id: playlistDialogs

            app: window
            host: overlay
        }

        ShortcutSheet {
            id: shortcutSheet

            host: overlay
        }

        SnackbarHost {
            id: snackbars

            objectName: "snackbars"
            anchors.fill: parent
        }

        OverlayLayer {
            id: overlay
        }

        // Window-wide shortcuts; playback ones come with the player capsule.
        Item {
            Shortcut {
                sequence: "Ctrl+F"
                onActivated: {
                    if (window.routeKind !== "search")
                        window.navigate("search:" + search.text);
                    // After the page swap, which may move focus into the new page.
                    Qt.callLater(() => {
                        search.forceFocus();
                        search.input.selectAll();
                    });
                }
            }
            Shortcut {
                sequence: "Ctrl+K"
                onActivated: {
                    if (window.routeKind !== "search")
                        window.navigate("search:" + search.text);
                    // After the page swap, which may move focus into the new page.
                    Qt.callLater(() => {
                        search.forceFocus();
                        search.input.selectAll();
                    });
                }
            }
            Shortcut {
                sequence: "Alt+Left"
                onActivated: window.goBack()
            }
            Shortcut {
                sequence: "Alt+Right"
                onActivated: window.goForward()
            }
            Shortcut {
                sequence: "F1"
                onActivated: shortcutSheet.open()
            }
            Shortcut {
                sequence: "Ctrl+J"
                onActivated: window.focusContent()
            }
            Shortcut {
                sequence: "Ctrl+N"
                onActivated: playlistDialogs.newPlaylist([])
            }
            Shortcut {
                sequence: "Ctrl+Left"
                onActivated: player.previous()
            }
            Shortcut {
                sequence: "Ctrl+Right"
                onActivated: player.next()
            }
            Shortcut {
                sequence: "Ctrl+Up"
                onActivated: player.changeVolume(5)
            }
            Shortcut {
                sequence: "Ctrl+Down"
                onActivated: player.changeVolume(-5)
            }
            Shortcut {
                sequence: "Ctrl+Space"
                onActivated: player.toggle()
            }
            Shortcut {
                sequence: "Media Play"
                onActivated: player.toggle()
            }
            Shortcut {
                sequence: "Ctrl+S"
                onActivated: player.setShuffle(!player.shuffle)
            }
            Shortcut {
                sequence: "Ctrl+R"
                onActivated: player.cycleRepeat()
            }
            Shortcut {
                sequence: "Ctrl+Shift+F"
                onActivated: player.toggleFavorite()
            }
            Shortcut {
                sequence: "Ctrl+P"
                onActivated: window.togglePanel("now")
            }
            Shortcut {
                sequence: "Ctrl+L"
                onActivated: window.togglePanel("lyrics")
            }
            Shortcut {
                sequence: "Ctrl+Q"
                onActivated: window.togglePanel("queue")
            }
            Shortcut {
                sequence: "Alt+1"
                onActivated: window.navigate("home")
            }
            Shortcut {
                sequence: "Alt+2"
                onActivated: window.navigate("collection:favorites")
            }
            Shortcut {
                sequence: "Alt+3"
                onActivated: window.navigate("library:artists")
            }
            Shortcut {
                sequence: "Alt+4"
                onActivated: window.navigate("downloads")
            }
            Shortcut {
                sequence: "Alt+5"
                onActivated: {
                    window.navigate("downloads");
                    typeof addMusic !== "undefined" && addMusic.importFiles();
                }
            }
    
        }
    }
}
