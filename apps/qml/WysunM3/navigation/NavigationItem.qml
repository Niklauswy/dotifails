// One destination of a NavigationDrawer ("drawer": 56 high, full-width pill indicator, label-large, trailing
// badge count) or a NavigationRail ("rail": a 56 x 32 indicator that grows from 32 when it becomes active, the
// label-medium label below, a Badge on the icon). The icon turns filled when active.
// destination: {id, icon, activeIcon?, label, badge?, trailing?, image?, trailingIcon?, railLabel?, railIcon?};
// `image` (e.g. a playlist cover) replaces the drawer icon, `trailingIcon` follows the label (e.g. a now-playing
// mark), `railLabel`/`railIcon` shorten a destination in the rail. Right click emits contextRequested in window
// coordinates.
import QtQuick
import WysunM3

Item {
    id: root

    property string mode: "drawer"           // drawer | rail
    property var destination: ({})
    property bool active
    readonly property bool drawer: mode !== "rail"
    readonly property string destinationId: destination.id ?? ""
    readonly property bool iconFilled: active
    readonly property color contentColor: active ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
    readonly property string trailingText: destination.trailing ?? (typeof destination.badge === "number" && destination.badge > 0 ? (destination.badge > Metrics.badgeMaxCount ? Metrics.badgeMaxCount + "+" : String(destination.badge)) : "")
    readonly property string iconName: !drawer && destination.railIcon ? destination.railIcon : active && destination.activeIcon ? destination.activeIcon : destination.icon ?? ""
    readonly property string image: drawer ? destination.image ?? "" : ""

    signal clicked
    signal stepRequested(int delta)
    signal contextRequested(real x, real y)

    function _press(mouse) {
        if (mouse.button === Qt.RightButton) {
            const point = mapToItem(null, mouse.x, mouse.y);
            contextRequested(point.x, point.y);
        } else {
            clicked();
        }
    }

    objectName: "nav-" + destinationId
    implicitWidth: drawer ? Metrics.drawerWidth : Metrics.railWidth
    implicitHeight: drawer ? Metrics.drawerItemHeight : railColumn.implicitHeight
    focusPolicy: Qt.TabFocus
    activeFocusOnTab: true

    Keys.onPressed: event => {
        switch (event.key) {
        case Qt.Key_Space:
        case Qt.Key_Return:
        case Qt.Key_Enter:
            root.clicked();
            break;
        case Qt.Key_Up:
            root.stepRequested(-1);
            break;
        case Qt.Key_Down:
            root.stepRequested(1);
            break;
        default:
            return;
        }
        event.accepted = true;
    }

    // --- drawer ------------------------------------------------------------------------------------------
    Rectangle {
        id: pill

        visible: root.drawer
        anchors.fill: parent
        radius: Theme.fullRadius(height)
        color: root.active ? Theme.m3secondaryContainer : "transparent"

        Behavior on color {
            CAnim {
                kind: "fastEffects"
            }
        }

        Row {
            x: Theme.padding.large ?? 0
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 2 * x
            spacing: Theme.spacing.medium ?? 0

            Item {
                anchors.verticalCenter: parent.verticalCenter
                width: Metrics.iconSize
                height: Metrics.iconSize

                Icon {
                    anchors.centerIn: parent
                    visible: root.image === ""
                    name: root.iconName
                    filled: root.iconFilled
                    color: root.contentColor
                }

                Image {
                    objectName: "navImage"
                    anchors.fill: parent
                    visible: root.image !== ""
                    source: root.image
                    asynchronous: true
                    fillMode: Image.PreserveAspectCrop
                    sourceSize.width: width * 2
                    sourceSize.height: height * 2
                }
            }

            Label {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - Metrics.iconSize - parent.spacing - (trail.visible ? trail.implicitWidth + parent.spacing : 0) - (trailIcon.visible ? Metrics.iconSize + parent.spacing : 0)
                role: "label.large"
                text: root.destination.label ?? ""
                color: root.contentColor
                elide: Text.ElideRight
            }

            Label {
                id: trail

                anchors.verticalCenter: parent.verticalCenter
                visible: text !== ""
                role: "label.large"
                text: root.trailingText
                color: root.contentColor
            }

            Icon {
                id: trailIcon

                objectName: "navTrailingIcon"
                anchors.verticalCenter: parent.verticalCenter
                visible: (root.destination.trailingIcon ?? "") !== "" && available
                name: root.destination.trailingIcon ?? ""
                color: root.active ? root.contentColor : Theme.m3primary
            }
        }

        StateLayer {
            tint: root.contentColor
            radius: pill.radius
            focused: root.activeFocus
            mouseArea.acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: mouse => root._press(mouse)
        }

        FocusRing {
            target: pill
            visible: root.drawer && root.activeFocus
        }
    }

    // --- rail --------------------------------------------------------------------------------------------
    Column {
        id: railColumn

        visible: !root.drawer
        width: parent.width
        spacing: Theme.spacing.extraSmall ?? 0

        Item {
            id: target

            readonly property real radius: Theme.fullRadius(height)

            anchors.horizontalCenter: parent.horizontalCenter
            width: Metrics.railIndicatorWidth
            height: Metrics.railIndicatorHeight

            Rectangle {
                objectName: root.drawer ? "" : "indicator-" + root.destinationId
                anchors.centerIn: parent
                width: root.active ? Metrics.railIndicatorWidth : Metrics.railIndicatorHeight
                height: Metrics.railIndicatorHeight
                radius: Theme.fullRadius(height)
                color: Theme.m3secondaryContainer
                opacity: root.active ? 1 : 0

                SpringBehavior on width {
                    kind: "fastSpatial"
                }
                SpringBehavior on opacity {
                    kind: "fastEffects"
                }
            }

            Icon {
                id: railIcon

                anchors.centerIn: parent
                name: root.iconName
                filled: root.iconFilled
                color: root.contentColor
            }

            Badge {
                objectName: root.drawer ? "" : "badge-" + root.destinationId
                visible: root.destination.badge !== undefined && root.destination.badge !== false
                count: typeof root.destination.badge === "number" ? root.destination.badge : 0
                x: railIcon.x + railIcon.width - width / 2
                y: railIcon.y - height / 3
            }

            StateLayer {
                tint: root.contentColor
                radius: target.radius
                focused: root.activeFocus
                mouseArea.acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: mouse => root._press(mouse)
            }

            FocusRing {
                target: target
                visible: !root.drawer && root.activeFocus
            }
        }

        Label {
            objectName: root.drawer ? "" : "label-" + root.destinationId
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(implicitWidth, root.width)
            role: "label.medium"
            text: root.destination.railLabel ?? root.destination.label ?? ""
            color: root.active ? Theme.m3onSurface : Theme.m3onSurfaceVariant
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
        }
    }
}
