// M3 tabs, 48 high (64 with icons): "primary" for top-level views of the content below (a 3 px indicator as wide
// as the label, active in primary), "secondary" inside a view (a 2 px indicator across the whole tab).
// tabs: [{id, text, icon?}]. ←/→ move between tabs while the bar has focus.
import QtQuick
import WysunM3

Item {
    id: root

    property string variant: "primary"       // primary | secondary
    property var tabs: []
    property string currentId
    readonly property bool primary: variant !== "secondary"
    readonly property bool withIcons: primary && tabs.some(t => !!t.icon)
    readonly property int currentIndex: Math.max(0, tabs.findIndex(t => t.id === currentId))
    readonly property real tabWidth: tabs.length > 0 ? width / tabs.length : 0
    readonly property int indicatorHeight: primary ? Metrics.tabIndicatorPrimary : Metrics.tabIndicatorSecondary
    readonly property real indicatorWidth: primary ? Math.max(Metrics.tabIndicatorMinWidth, row.itemAt(currentIndex)?.contentWidth ?? 0) : tabWidth
    readonly property real indicatorX: currentIndex * tabWidth + (tabWidth - indicatorWidth) / 2

    signal activated(string id)

    function select(index) {
        const tab = tabs[Math.max(0, Math.min(tabs.length - 1, index))];
        if (!tab || tab.id === currentId)
            return;
        currentId = tab.id;
        activated(tab.id);
    }

    implicitHeight: withIcons ? Metrics.tabHeightWithIcon : Metrics.tabHeight
    height: implicitHeight
    focusPolicy: Qt.TabFocus
    activeFocusOnTab: true

    Keys.onLeftPressed: select(currentIndex - 1)
    Keys.onRightPressed: select(currentIndex + 1)

    Repeater {
        id: row

        model: root.tabs

        Item {
            id: tab

            required property var modelData
            required property int index
            readonly property bool active: index === root.currentIndex
            readonly property real contentWidth: content.width
            readonly property color contentColor: active ? (root.primary ? Theme.m3primary : Theme.m3onSurface) : Theme.m3onSurfaceVariant

            x: index * root.tabWidth
            width: root.tabWidth
            height: root.height

            Column {
                id: content

                anchors.centerIn: parent
                spacing: Theme.spacing.extraSmall / 2 || 0

                Icon {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: root.withIcons && !!tab.modelData.icon
                    name: tab.modelData.icon ?? ""
                    filled: tab.active
                    color: tab.contentColor
                }

                Label {
                    anchors.horizontalCenter: parent.horizontalCenter
                    role: "title.small"
                    text: tab.modelData.text ?? ""
                    color: tab.contentColor
                }
            }

            StateLayer {
                tint: tab.contentColor
                onClicked: root.select(tab.index)
            }
        }
    }

    Divider {
        anchors.bottom: parent.bottom
        width: parent.width
    }

    Rectangle {
        x: root.indicatorX
        anchors.bottom: parent.bottom
        width: root.indicatorWidth
        height: root.indicatorHeight
        topLeftRadius: root.primary ? root.indicatorHeight : 0
        topRightRadius: root.primary ? root.indicatorHeight : 0
        color: Theme.m3primary

        SpringBehavior on x {
            kind: "fastSpatial"
        }
        SpringBehavior on width {
            kind: "fastSpatial"
        }
    }

    FocusRing {
        target: root
    }
}
