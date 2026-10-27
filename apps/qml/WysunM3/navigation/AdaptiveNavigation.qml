// Navigation that follows the window size class (Metrics.windowClass): below 600 the content takes the whole
// width and a modal drawer opens from the app's menu button (`menuButtonVisible`, openModal()); 600-839 a rail;
// 840 and up a standard drawer. Children are the content; the content area slides with the fast spatial spring
// when the class changes. Growing out of "modal" closes the modal drawer and gives focus back.
import QtQuick
import WysunM3

Item {
    id: root

    property real windowWidth: width
    property var destinations: []
    property string currentId
    property Component header                // drawers: e.g. an extended Fab
    property Component fab                   // rail
    default property alias content: contentArea.data
    readonly property string mode: Metrics.windowClass(windowWidth)
    readonly property bool menuButtonVisible: mode === "modal"
    property bool modalOpen
    property Item _returnFocus

    signal destinationSelected(string id)
    signal headerAction(string actionId)
    signal contextRequested(string id, real x, real y)

    function openModal() {
        if (mode !== "modal" || modalOpen)
            return;
        _returnFocus = Window.activeFocusItem;
        modalOpen = true;
        modal.item?.focusCurrent();
    }

    function closeModal() {
        if (!modalOpen)
            return;
        modalOpen = false;
        const back = _returnFocus;
        _returnFocus = null;
        if (back)
            back.forceActiveFocus(Qt.TabFocusReason);
    }

    function select(id) {
        destinationSelected(id);
        closeModal();
    }

    onModeChanged: {
        if (mode !== "modal")
            closeModal();
    }

    Loader {
        active: root.mode === "standard"
        height: parent.height
        sourceComponent: NavigationDrawer {
            height: root.height
            destinations: root.destinations
            currentId: root.currentId
            header: root.header
            onSelected: id => root.select(id)
            onHeaderAction: id => root.headerAction(id)
            onContextRequested: (id, x, y) => root.contextRequested(id, x, y)
        }
    }

    Loader {
        active: root.mode === "rail"
        height: parent.height
        sourceComponent: NavigationRail {
            height: root.height
            destinations: root.destinations
            currentId: root.currentId
            fab: root.fab
            onSelected: id => root.select(id)
            onContextRequested: (id, x, y) => root.contextRequested(id, x, y)
        }
    }

    Item {
        id: contentArea

        objectName: "content"
        x: root.mode === "standard" ? Metrics.drawerWidth : root.mode === "rail" ? Metrics.railWidth : 0
        width: root.width - x
        height: root.height

        SpringBehavior on x {
            kind: "fastSpatial"
        }
    }

    Rectangle {
        anchors.fill: parent
        color: Qt.alpha(Theme.m3scrim, Metrics.scrimOpacity)
        opacity: root.modalOpen ? 1 : 0
        visible: opacity > 0

        SpringBehavior on opacity {
            kind: "fastEffects"
        }

        MouseArea {
            anchors.fill: parent
            onClicked: root.closeModal()
        }
    }

    Loader {
        id: modal

        active: root.mode === "modal"
        height: parent.height
        x: root.modalOpen ? 0 : -Metrics.drawerWidth - Metrics.modalDrawerElevation * (Theme.padding.small ?? 0)
        visible: root.modalOpen || x > -Metrics.drawerWidth

        SpringBehavior on x {
            kind: "fastSpatial"
        }

        sourceComponent: NavigationDrawer {
            height: root.height
            variant: "modal"
            destinations: root.destinations
            currentId: root.currentId
            header: root.header
            enabled: root.modalOpen
            onSelected: id => root.select(id)
            onCloseRequested: root.closeModal()
            onHeaderAction: id => root.headerAction(id)
            onContextRequested: (id, x, y) => root.contextRequested(id, x, y)
        }
    }
}
