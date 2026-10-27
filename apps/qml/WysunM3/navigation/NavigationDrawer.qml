// M3 navigation drawer, 280 wide on surfaceContainerLow with the large corner on its end side. destinations:
// [{id, icon, activeIcon?, label, badge?, trailing?}], with {header: "text"} section titles (title-small,
// onSurfaceVariant; `action`/`actionId` add an icon button to it that emits headerAction) and {divider: true}
// separators; `drawer: false` keeps a destination in the rail only. `header` (e.g. an extended Fab) goes on top. "standard" sits
// beside the content; "modal" floats over it (elevation 1) and asks to close on Escape. ↑/↓ move between
// destinations, Enter/Space select.
import QtQuick
import WysunM3

Surface {
    id: root

    property var destinations: []
    property string currentId
    property Component header
    property string variant: "standard"      // standard | modal

    signal selected(string id)
    signal closeRequested
    signal headerAction(string actionId)
    signal contextRequested(string id, real x, real y)
    readonly property var drawerDestinations: destinations.filter(d => d.drawer !== false)

    function itemFor(id) {
        for (let i = 0; i < entries.count; ++i) {
            const item = entries.itemAt(i)?.navItem;
            if (item && item.destinationId === id)
                return item;
        }
        return null;
    }

    function step(fromId, delta) {
        const ids = [];
        for (const d of drawerDestinations)
            if (d.id !== undefined)
                ids.push(d.id);
        const at = ids.indexOf(fromId);
        const next = ids[Math.max(0, Math.min(ids.length - 1, at + delta))];
        itemFor(next)?.forceActiveFocus(Qt.TabFocusReason);
    }

    function focusCurrent() {
        (itemFor(currentId) ?? itemFor(destinations.find(d => d.id !== undefined)?.id))?.forceActiveFocus(Qt.TabFocusReason);
    }

    objectName: "drawer"
    implicitWidth: Metrics.drawerWidth
    width: implicitWidth
    container: Theme.m3surfaceContainerLow
    color: container
    level: variant === "modal" ? Metrics.modalDrawerElevation : 0
    topRightRadius: Theme.rounding.large ?? 0
    bottomRightRadius: Theme.rounding.large ?? 0

    Keys.onEscapePressed: event => {
        if (variant === "modal")
            closeRequested();
        else
            event.accepted = false;
    }

    // Swallow clicks so a modal drawer never lets them through to the scrim.
    MouseArea {
        anchors.fill: parent
    }

    Flickable {
        anchors.fill: parent
        anchors.margins: Theme.padding.medium ?? 0
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: column

            width: parent.width

            Loader {
                active: root.header !== null
                sourceComponent: root.header
            }

            Repeater {
                id: entries

                model: root.drawerDestinations

                Item {
                    id: entry

                    required property var modelData
                    required property int index
                    readonly property Item navItem: loader.item instanceof NavigationItem ? loader.item : null

                    width: column.width
                    height: loader.height

                    Loader {
                        id: loader

                        width: parent.width
                        sourceComponent: entry.modelData.header !== undefined ? headerEntry : entry.modelData.divider ? dividerEntry : destinationEntry
                    }

                    Component {
                        id: headerEntry

                        Item {
                            width: column.width
                            height: headerLabel.implicitHeight + (Theme.padding.large ?? 0) + (Theme.padding.small ?? 0)

                            Label {
                                id: headerLabel

                                objectName: "header-" + entry.modelData.header
                                x: Theme.padding.large ?? 0
                                y: Theme.padding.large ?? 0
                                role: "title.small"
                                text: entry.modelData.header
                                color: Theme.m3onSurfaceVariant
                            }

                            IconButton {
                                objectName: "headerAction-" + (entry.modelData.actionId ?? "")
                                anchors.right: parent.right
                                anchors.verticalCenter: headerLabel.verticalCenter
                                visible: !!entry.modelData.action
                                icon: entry.modelData.action ?? ""
                                onClicked: root.headerAction(entry.modelData.actionId ?? "")

                                Tooltip {
                                    text: entry.modelData.actionLabel ?? ""
                                    visible: text !== ""
                                }
                            }
                        }
                    }

                    Component {
                        id: dividerEntry

                        Item {
                            width: column.width
                            height: 2 * (Theme.padding.small ?? 0) + Metrics.outlineWidth

                            Divider {
                                objectName: "divider-" + entry.index
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width
                                inset: "both"
                            }
                        }
                    }

                    Component {
                        id: destinationEntry

                        NavigationItem {
                            width: column.width
                            mode: "drawer"
                            destination: entry.modelData
                            active: root.currentId === destinationId
                            onClicked: root.selected(destinationId)
                            onStepRequested: delta => root.step(destinationId, delta)
                            onContextRequested: (x, y) => root.contextRequested(destinationId, x, y)
                        }
                    }
                }
            }
        }
    }
}
