// M3 navigation rail, 80 wide: an optional menu button (opens the modal drawer), an optional `fab`, then the
// destinations (3-7 is best; those with `rail: false`, headers and dividers stay in the drawers).
import QtQuick
import WysunM3

Item {
    id: root

    property var destinations: []
    property string currentId
    property bool menuButton
    property Component fab
    // `railOrder` reorders the rail without touching the drawer's order.
    readonly property var railDestinations: destinations.filter(d => d.id !== undefined && d.rail !== false).map((d, i) => ({
                d: d,
                i: i
            })).sort((a, b) => (a.d.railOrder ?? a.i) - (b.d.railOrder ?? b.i) || a.i - b.i).map(e => e.d)

    signal selected(string id)
    signal menuRequested
    signal contextRequested(string id, real x, real y)

    function step(fromId, delta) {
        const ids = railDestinations.map(d => d.id);
        const next = ids[Math.max(0, Math.min(ids.length - 1, ids.indexOf(fromId) + delta))];
        for (let i = 0; i < items.count; ++i)
            if (items.itemAt(i).destinationId === next)
                items.itemAt(i).forceActiveFocus(Qt.TabFocusReason);
    }

    objectName: "rail"
    implicitWidth: Metrics.railWidth
    width: implicitWidth

    Column {
        y: Theme.padding.medium ?? 0
        width: parent.width
        spacing: Theme.spacing.medium ?? 0

        IconButton {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.menuButton
            icon: "menu"
            onClicked: root.menuRequested()
        }

        Loader {
            anchors.horizontalCenter: parent.horizontalCenter
            active: root.fab !== null
            sourceComponent: root.fab
        }

        Repeater {
            id: items

            model: root.railDestinations

            NavigationItem {
                required property var modelData

                width: root.width
                mode: "rail"
                destination: modelData
                active: root.currentId === destinationId
                onClicked: root.selected(destinationId)
                onStepRequested: delta => root.step(destinationId, delta)
                onContextRequested: (x, y) => root.contextRequested(destinationId, x, y)
            }
        }
    }
}
