// The WysunM3 gallery window (python3 -m wysun_qml): every component on an adaptive navigation, pages switched
// with fade through, a palette menu and a light/dark switch that preview on the live theme.
import QtQuick
import WysunM3

Window {
    id: window

    property string page: galleryOptions.page
    readonly property var destinations: [
        {header: "Base"},
        {id: "theme", icon: "palette", label: "Tema"},
        {id: "motion", icon: "animation", label: "Movimiento"},
        {divider: true},
        {header: "Componentes"},
        {id: "buttons", icon: "smart_button", label: "Botones"},
        {id: "chips", icon: "interests", label: "Chips y formas"},
        {id: "fields", icon: "text_fields", label: "Campos y búsqueda"},
        {id: "lists", icon: "list", label: "Listas y tarjetas", badge: 10000},
        {id: "navigation", icon: "menu_open", label: "Navegación"},
        {id: "overlays", icon: "layers", label: "Superposiciones"},
        {id: "empty", icon: "inbox", label: "Estados vacíos"},
        {id: "live", icon: "monitoring", label: "Datos en vivo"}
    ]
    readonly property var files: ({
            theme: "ThemePage.qml",
            motion: "MotionPage.qml",
            buttons: "ButtonsPage.qml",
            chips: "ChipsPage.qml",
            fields: "FieldsPage.qml",
            lists: "ListsPage.qml",
            navigation: "NavigationPage.qml",
            overlays: "OverlaysPage.qml",
            empty: "EmptyPage.qml",
            live: "LivePage.qml"
        })
    readonly property Item currentPage: pages.currentItem

    signal benchFinished(var result)

    function labelOf(id) {
        return destinations.find(d => d.id === id)?.label ?? "";
    }

    function showPage(id) {
        if (!files[id])
            return;
        page = id;
        const component = Qt.createComponent(Qt.resolvedUrl("pages/" + files[id]));
        if (component.status !== Component.Ready) {
            console.warn("gallery: " + component.errorString());
            return;
        }
        pages.show(component, {
            snackbars: snackbars,
            overlay: overlay,
            windowWidth: Qt.binding(() => window.width)
        }, true);
    }

    title: galleryOptions.title
    width: galleryOptions.width
    height: galleryOptions.height
    visible: true
    color: Theme.m3surface

    Component.onCompleted: {
        showPage(page);
        if (galleryOptions.bench)
            bench.start();
    }

    Item {
        id: root

        anchors.fill: parent

        ThemeFeed {
            scheme: bridge.scheme
            tokens: bridge.tokens
            reducedMotion: bridge.reducedMotion
        }

        AdaptiveNavigation {
            id: nav

            objectName: "galleryNav"
            anchors.fill: parent
            destinations: window.destinations
            currentId: window.page
            onDestinationSelected: id => window.showPage(id)
            header: Component {
                Fab {
                    id: paletteFab

                    extended: true
                    variant: "tertiary"
                    icon: "format_paint"
                    text: "Paleta"
                    onClicked: paletteMenu.popup(paletteFab, 0, paletteFab.height)
                }
            }
            fab: Component {
                Fab {
                    id: railPaletteFab

                    variant: "tertiary"
                    icon: "format_paint"
                    onClicked: paletteMenu.popup(railPaletteFab, railPaletteFab.width, 0)
                }
            }

            TopAppBar {
                id: bar

                width: parent.width
                title: window.labelOf(window.page)
                scrollOffset: window.currentPage?.scrollOffset ?? 0
                leading: Component {
                    IconButton {
                        visible: nav.menuButtonVisible
                        icon: "menu"
                        onClicked: nav.openModal()
                    }
                }
                actions: Component {
                    Row {
                        spacing: Theme.spacing.small ?? 0

                        SegmentedButtons {
                            anchors.verticalCenter: parent.verticalCenter
                            visible: window.width >= Metrics.windowMedium
                            model: [{value: "light", icon: "light_mode", text: "Claro"}, {value: "dark", icon: "dark_mode", text: "Oscuro"}]
                            current: gallery.mode
                            onActivated: value => gallery.setMode(value)
                        }
                        IconButton {
                            anchors.verticalCenter: parent.verticalCenter
                            visible: window.width < Metrics.windowMedium
                            icon: gallery.mode === "dark" ? "light_mode" : "dark_mode"
                            onClicked: gallery.setMode(gallery.mode === "dark" ? "light" : "dark")
                        }
                    }
                }
            }

            FadeThrough {
                id: pages

                objectName: "pages"
                y: bar.height
                width: parent.width
                height: parent.height - bar.height
                clip: true
            }
        }

        Menu {
            id: paletteMenu

            host: overlay
            model: gallery.palettes.map(name => ({
                        id: name,
                        text: ({live: "Wallpaper actual", default: "Base", green: "Verde", orange: "Naranja", blue: "Azul"})[name] ?? name,
                        icon: name === gallery.palette ? "check" : "palette"
                    }))
            onTriggered: id => gallery.setPalette(id)
        }

        SnackbarHost {
            id: snackbars

            anchors.fill: parent
        }

        OverlayLayer {
            id: overlay
        }

        Bench {
            id: bench

            window: window
            view: window.currentPage?.benchView ?? null
            onFinished: result => window.benchFinished(result)
            onNeedsList: window.showPage("lists")
        }
    }
}
